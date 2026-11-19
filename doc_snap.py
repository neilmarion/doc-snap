#!/usr/bin/env python3
"""doc-snap: one-press webcam capture of documents for LLMs.

Keys:  SPACE / ENTER / click CAPTURE button = take photo
       G = toggle grayscale    O = open output folder    Q / ESC = quit
"""
import argparse
import json
import re
import subprocess
import sys
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


def find_camera_index():
    """Return the AVFoundation index of a Logitech-looking camera, else None."""
    try:
        out = subprocess.run(
            ["ffmpeg", "-hide_banner", "-f", "avfoundation", "-list_devices", "true", "-i", ""],
            capture_output=True, text=True, timeout=10,
        ).stderr
    except Exception:
        return None
    video = out.split("audio devices")[0]
    for idx, name in re.findall(r"\[(\d+)\] (.+)", video):
        if CAMERA_HINTS.search(name):
            print(f"Using camera [{idx}] {name.strip()}")
            return int(idx)
    return None


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
    p.add_argument("--camera", type=int, help="Camera index (default: auto-detect Logitech)")
    p.add_argument("--max-side", type=int, default=cfg.get("max_side", 1280), help="Longest side in px (default 1280)")
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
    idx = a.camera if a.camera is not None else find_camera_index()
    if idx is None:
        print("Logitech camera not found by name. Using camera 0. Use --camera N to pick another.")
        idx = 0

    cap = cv2.VideoCapture(idx, cv2.CAP_AVFOUNDATION)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
    if not cap.isOpened():
        sys.exit("Could not open camera. Check System Settings > Privacy & Security > Camera for your terminal app.")

    state = {"snap": False}

    def on_mouse(event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN and y >= param["h"] - BTN_H:
            state["snap"] = True

    mouse_param = {"h": 0}
    cv2.namedWindow(WIN, cv2.WINDOW_NORMAL)
    cv2.setMouseCallback(WIN, on_mouse, mouse_param)

    count, last_name, flash_until = 0, "", 0.0
    gray = a.gray
    while True:
        ok, frame = cap.read()
        if not ok:
            time.sleep(0.01)
            continue

        if state["snap"]:
            state["snap"] = False
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
        status = f"{count} saved{'  | last: ' + last_name if last_name else ''}  | {'GRAY' if gray else 'COLOR'}"
        cv2.putText(view, status, (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 4)
        cv2.putText(view, status, (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 1)
        cv2.imshow(WIN, view)

        key = cv2.waitKey(1) & 0xFF
        if key in (32, 13):
            state["snap"] = True
        elif key in (ord("q"), 27):
            break
        elif key == ord("g"):
            gray = not gray
            cfg["gray"] = gray
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
