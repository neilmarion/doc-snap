#!/usr/bin/env python3
"""doc-snap: one-press webcam capture of documents for LLMs.

Keys:  SPACE / ENTER / click CAPTURE button = take photo
       C = switch camera   R = rotate 90°   G = toggle grayscale    O = open output folder    Q / ESC = quit
"""
import argparse
import json
import re
import subprocess
import sys
import threading
import time
import wave
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

APP_DIR = Path(__file__).resolve().parent
CONFIG = APP_DIR / "config.json"
CLICK_WAV = APP_DIR / "click.wav"
WIN = "doc-snap"
BTN_H = 70
CAMERA_HINTS = re.compile(r"logi|brio|c9\d\d|c270|c310|streamcam|webcam", re.I)


def load_config():
    if CONFIG.exists():
        try:
            return json.loads(CONFIG.read_text())
        except Exception:
            pass
    return {}


def save_config(cfg):
    CONFIG.write_text(json.dumps(cfg, indent=2))


def camera_names():
    """All video cameras by name (ffmpeg/AVFoundation, incl. iPhone Continuity Camera)."""
    try:
        out = subprocess.run(
            ["ffmpeg", "-hide_banner", "-f", "avfoundation", "-list_devices", "true", "-i", ""],
            capture_output=True, text=True, timeout=10,
        ).stderr
    except Exception:
        return []
    video = out.split("audio devices")[0]
    return [n.strip() for _, n in re.findall(r"\[(\d+)\] (.+)", video) if not n.startswith("Capture screen")]


def find_camera_index(names):
    """Return index of a Logitech-looking camera, else None."""
    for idx, name in enumerate(names):
        if CAMERA_HINTS.search(name):
            return idx
    return None


class FFCam:
    """Reads frames from a camera by name through ffmpeg. Keeps only the newest frame."""

    def __init__(self, name):
        self.name, self.frame, self.proc, self.error = name, None, None, ""
        if not self._start(["-framerate", "30", "-video_size", "1920x1080"]):
            mode = self._best_mode(self.error)
            if not (mode and self._start(["-framerate", mode[2], "-video_size", f"{mode[0]}x{mode[1]}"])):
                self._start([])

    @staticmethod
    def _best_mode(err):
        modes = re.findall(r"(\d+)x(\d+)@\[[\d.]+ ([\d.]+)\]fps", err)
        modes = [m for m in modes if int(m[0]) <= 1920] or modes
        if not modes:
            return None
        return max(modes, key=lambda m: (int(m[0]) * int(m[1]), float(m[2])))

    def _start(self, opts):
        self.release()
        cmd = ["ffmpeg", "-hide_banner", "-loglevel", "info", "-f", "avfoundation", *opts,
               "-i", f"{self.name}:none", "-fps_mode", "passthrough", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"]
        self.proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        err, size = "", None
        for raw in iter(self.proc.stderr.readline, b""):
            line = raw.decode(errors="replace")
            err += line
            m = re.search(r"Stream #0:0.*rawvideo.*?(\d{3,5})x(\d{3,5})", line) if "bgr24" in line else None
            if m:
                size = (int(m.group(1)), int(m.group(2)))
                break
        self.error = err
        if not size:
            self.release()
            return False
        self.w, self.h = size
        threading.Thread(target=self._drain_err, daemon=True).start()
        threading.Thread(target=self._read, daemon=True).start()
        return True

    def _drain_err(self):
        proc = self.proc
        for _ in iter(proc.stderr.readline, b""):
            pass

    def _read(self):
        proc, n = self.proc, self.w * self.h * 3
        while proc and proc.poll() is None:
            buf = proc.stdout.read(n)
            if not buf or len(buf) < n:
                break
            self.frame = np.frombuffer(buf, np.uint8).reshape(self.h, self.w, 3)

    def isOpened(self):
        return self.proc is not None and self.proc.poll() is None

    def read(self):
        f = self.frame
        return (f is not None), f

    def release(self):
        if self.proc:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=2)
            except Exception:
                self.proc.kill()
        self.proc, self.frame = None, None


def make_click_sound():
    """Write a short shutter-click WAV once."""
    if CLICK_WAV.exists():
        return
    sr = 44100
    t = np.arange(int(sr * 0.06)) / sr
    rng = np.random.default_rng(1)
    click = rng.uniform(-1, 1, t.size) * np.exp(-t * 90)
    click[int(sr * 0.025):] += rng.uniform(-1, 1, t.size - int(sr * 0.025)) * 0.6 * np.exp(-(t[: t.size - int(sr * 0.025)]) * 120)
    data = (np.clip(click, -1, 1) * 0.8 * 32767).astype(np.int16)
    with wave.open(str(CLICK_WAV), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(data.tobytes())


def play_click():
    subprocess.Popen(["afplay", str(CLICK_WAV)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def shrink(img, max_side):
    h, w = img.shape[:2]
    s = max_side / max(h, w)
    if s < 1:
        img = cv2.resize(img, (int(w * s), int(h * s)), interpolation=cv2.INTER_AREA)
    return img


def main():
    cfg = load_config()
    p = argparse.ArgumentParser(description="One-press document capture from webcam.")
    p.add_argument("--out", help="Folder to save photos (remembered for next time)")
    p.add_argument("--camera", type=int, help="Camera number from the list printed at start (default: last used, else Logitech)")
    p.add_argument("--max-side", type=int, default=cfg.get("max_side", 1920), help="Longest side in px (default 1920)")
    p.add_argument("--quality", type=int, default=cfg.get("quality", 70), help="JPEG quality 1-100 (default 70)")
    p.add_argument("--prefix", default=cfg.get("prefix", "doc"), help="File name prefix (default 'doc')")
    p.add_argument("--gray", action="store_true", default=cfg.get("gray", False), help="Save in grayscale")
    a = p.parse_args()

    out = Path(a.out or cfg.get("out") or Path.home() / "Pictures" / "doc-snap").expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)
    cfg.update(out=str(out), max_side=a.max_side, quality=a.quality, prefix=a.prefix, gray=a.gray)
    save_config(cfg)
    print(f"Saving to: {out}")

    make_click_sound()
    names = camera_names()
    print("Cameras:", ", ".join(f"[{i}] {n}" for i, n in enumerate(names)) or "unknown")
    idx = a.camera
    if idx is None and cfg.get("camera_name") in names:
        idx = names.index(cfg["camera_name"])  # last camera picked with C
    if idx is None:
        idx = find_camera_index(names)
    if idx is None:
        print("Logitech camera not found by name. Using camera 0. Press C to switch cameras.")
        idx = 0
    n_cams = max(len(names), 1)

    def open_cam(i):
        c = FFCam(names[i])
        print(f"Using camera [{i}] {names[i]}" + ("" if c.isOpened() else "  -> FAILED"))
        if not c.isOpened():
            print(c.error[-800:])
        return c

    if not names:
        sys.exit("No cameras found.")
    idx = min(idx, len(names) - 1)
    cap = open_cam(idx)
    if not cap.isOpened():
        print("Could not open camera. Check System Settings > Privacy & Security > Camera for your terminal app.")
        print("Press C in the window to try the next camera.")
    cam_label = names[idx] if idx < len(names) else f"camera {idx}"

    state = {}

    def on_mouse(event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN and y >= param["h"] - BTN_H:
            state["go"] = True

    mouse_param = {"h": 0}
    cv2.namedWindow(WIN, cv2.WINDOW_NORMAL)
    cv2.setMouseCallback(WIN, on_mouse, mouse_param)

    count, last_name, flash_until = 0, "", 0.0
    gray = a.gray
    rot = cfg.get("rotate", {}).get(cam_label, 0)  # quarter turns clockwise, per camera
    ROT = {1: cv2.ROTATE_90_CLOCKWISE, 2: cv2.ROTATE_180, 3: cv2.ROTATE_90_COUNTERCLOCKWISE}
    while True:
        ok, frame = cap.read()
        if not ok:
            frame = np.zeros((540, 960, 3), np.uint8)
            msg = "Starting camera..." if cap.isOpened() else "Camera failed - press C for next camera"
            cv2.putText(frame, msg, (30, 270), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2)

        if ok and rot:
            frame = cv2.rotate(frame, ROT[rot])
        if ok and state.pop("go", False):
            img = shrink(frame, a.max_side)
            if gray:
                img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            name = f"{a.prefix}_{datetime.now():%Y%m%d_%H%M%S_%f}"[:-3] + ".jpg"
            cv2.imwrite(str(out / name), img, [cv2.IMWRITE_JPEG_QUALITY, a.quality])
            play_click()
            count += 1
            last_name = name
            flash_until = time.time() + 0.15

        # preview
        view = shrink(frame, 960).copy()
        h, w = view.shape[:2]
        if time.time() < flash_until:
            view[:] = 255
        bar = np.full((BTN_H, w, 3), (40, 140, 40), np.uint8)
        cv2.putText(bar, "CAPTURE  (space)", (20, 45), cv2.FONT_HERSHEY_SIMPLEX, 1.1, (255, 255, 255), 2)
        view = np.vstack([view, bar])
        mouse_param["h"] = view.shape[0]
        status = f"{cam_label} | {count} saved{'  | last: ' + last_name if last_name else ''}  | {'GRAY' if gray else 'COLOR'}"
        cv2.putText(view, status, (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 4)
        cv2.putText(view, status, (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 1)
        cv2.imshow(WIN, view)

        key = cv2.waitKey(1) & 0xFF
        if key in (32, 13):
            state["go"] = True
        elif key in (ord("q"), 27):
            break
        elif key == ord("g"):
            gray = not gray
            cfg["gray"] = gray
            save_config(cfg)
        elif key == ord("c"):
            cap.release()
            names = camera_names() or names  # re-scan: picks up an iPhone that just appeared
            n_cams = len(names)
            print("Cameras:", ", ".join(f"[{i}] {n}" for i, n in enumerate(names)))
            idx = (idx + 1) % n_cams
            cap = open_cam(idx)
            cam_label = names[idx] if idx < len(names) else f"camera {idx}"
            rot = cfg.get("rotate", {}).get(cam_label, 0)
            if idx < len(names):
                cfg["camera_name"] = names[idx]  # remember for next start
                save_config(cfg)
        elif key == ord("r"):
            rot = (rot + 1) % 4
            cfg.setdefault("rotate", {})[cam_label] = rot
            save_config(cfg)
        elif key == ord("o"):
            subprocess.Popen(["open", str(out)])
        if cv2.getWindowProperty(WIN, cv2.WND_PROP_VISIBLE) < 1:
            break

    cap.release()
    cv2.destroyAllWindows()
    print(f"Done. {count} photo(s) in {out}")


if __name__ == "__main__":
    main()
