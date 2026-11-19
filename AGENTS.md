# AGENTS.md — instructions for an AI agent setting up doc-snap

You are an AI coding agent (Claude Code, Codex, Cursor, etc.) on a **new macOS laptop**.
Your job: install doc-snap, get a working camera, and confirm the photos are legible.
Read this whole file before you act. Follow the steps in order.

## What doc-snap is

A small Python app. It shows a live camera preview. One key press saves a JPEG.
Use: fast capture of student quiz sheets and other papers, to feed to an LLM.

- Entry point: `doc_snap.py`. Launcher: `doc-snap.command`, which creates `.venv` on first run.
- Cameras are read by **name** through `ffmpeg` (AVFoundation). OpenCV is used only for the window, rotation and JPEG encoding.
- Settings persist in `config.json` (git-ignored). It is created on first run.

## Hard facts (learned the hard way — do not re-learn them)

1. **macOS only.** Capture uses `ffmpeg -f avfoundation`.
2. **Do not use `cv2.VideoCapture` for cameras.** OpenCV cannot open Continuity Camera or Desk View devices. Its index order also differs from ffmpeg's. This was the cause of earlier bugs.
3. **Camera permission belongs to the app that starts the process.** If you run doc-snap from inside your own agent shell, macOS blocks the camera: `not authorized to capture video`. You cannot grant this permission yourself.
   - Always launch it in Terminal.app: `open -a Terminal /path/to/doc-snap/doc-snap.command`
   - The human must click **OK** on the camera prompt the first time. Then relaunch the app, because the first run exits before the permission is granted.
4. **To test without the GUI**, write a small script, launch it with `open -a Terminal script.command`, and have it write a log file you can read. That is the only way your process gets camera frames.
5. **Fixed-focus webcams** (e.g. Logitech Brio 100) are blurry closer than ~40–50 cm. Software cannot fix it, and Logitech apps have no focus control for them.

## Step 1 — Prerequisites

Check each one. Install what is missing.

```bash
xcode-select -p || xcode-select --install
```

```bash
which brew || echo "Install Homebrew first: https://brew.sh (the human must run it; it needs their password)"
```

```bash
brew install ffmpeg python
```

```bash
ffmpeg -version | head -1 && python3 --version
```

Python 3.10+ is enough.

## Step 2 — Get the code

```bash
mkdir -p ~/Dev && cd ~/Dev && git clone https://github.com/neilmarion/doc-snap.git && cd doc-snap
```

The repo is public, so no GitHub sign-in is needed to clone. To push changes, the human must sign in (for example `gh auth login`). Never type a password or token yourself.

## Step 3 — Install Python packages

```bash
cd ~/Dev/doc-snap && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
```

The launcher also does this when `.venv` is missing.

## Step 4 — See which cameras the Mac has

```bash
ffmpeg -hide_banner -f avfoundation -list_devices true -i "" 2>&1 | sed -n '/video devices/,/audio devices/p'
```

doc-snap shows the same names, minus `Capture screen N`.

Pick the camera with this priority:

| Camera | Good for documents? | Notes |
|---|---|---|
| `... Desk View Camera` | **Yes (proven)** | Top-down view of the desk in front of the laptop. Appears on Macs with a Center Stage camera (e.g. MacBook Air M4), or with an iPhone via Continuity Camera. |
| iPhone (Continuity Camera) | **Yes, best** | Autofocus. Needs same Apple ID, Wi-Fi + Bluetooth on, iPhone locked, still, near the Mac. No install, no cable. |
| Built-in FaceTime camera | Poor | Faces the user, not the paper. |
| Fixed-focus USB webcam | Only at 40–50 cm | Needs an arm or stand pointing down. |

If no Desk View and no iPhone shows up, tell the human. Do not continue with a camera that gives blurry text.

### Apple Silicon M1 MacBooks (and other Macs without a Center Stage camera)

The M1 MacBook Air and Pro have a 720p FaceTime camera with **no Center Stage**. So there is **no built-in Desk View**, and the proven MacBook Air setup below does not apply as-is. Use one of these:

1. **iPhone with Continuity Camera (recommended).**
   - Needs macOS 13 Ventura or later and iOS 16 or later.
   - **Desk View from an iPhone needs an iPhone 11 or later.** Plain iPhone camera works from iPhone XR.
   - Mount the iPhone on the laptop lid with a Continuity Camera clip (or any phone stand), back camera facing the paper.
   - In doc-snap, press **C** until the iPhone or `... Desk View Camera` shows. Prefer the iPhone camera pointing down if a stand is available: it has autofocus and the paper can fill the frame.
   - Check first that macOS sees it: Photo Booth → **Camera** menu.
2. **USB webcam on an arm, pointing down at 40–50 cm** (fixed focus) or a webcam with autofocus.

Check the macOS version first:

```bash
sw_vers -productVersion
```

If it is below 13, Continuity Camera is not available. Tell the human, and use option 2 or update macOS.

## Step 5 — Launch

```bash
open -a Terminal ~/Dev/doc-snap/doc-snap.command
```

Ask the human to click **OK** on the camera prompt. If the window says the camera failed, or Terminal printed `not authorized`, relaunch once after they allow it.

Optional first-run flags (each value is remembered in `config.json`):

```bash
~/Dev/doc-snap/doc-snap.command --out ~/Documents/quiz-photos
```

| Flag | Default | Meaning |
|---|---|---|
| `--out DIR` | `~/Pictures/doc-snap` | Save folder |
| `--camera N` | last used, else a Logitech-like name | Index in the camera list printed at start |
| `--max-side PX` | 1920 | Longest side of the saved JPEG |
| `--quality Q` | 70 | JPEG quality |
| `--prefix NAME` | `doc` | File name prefix |
| `--gray` | off | Save grayscale |

## Step 6 — Physical setup (tell the human)

For **Desk View** (proven to give legible handwriting on a MacBook Air M4 with its built-in Desk View; with an iPhone Desk View the steps are the same, but the tilt angle may differ):

1. In the doc-snap window, press **C** until the top line says `... Desk View Camera`. It is remembered.
2. Laptop on a **table**, not on a lap.
3. Tilt the screen to about **100°**, nearly upright. Do not tilt it back: tilting back points the camera away from the desk.
4. Lay the sheet flat, right in front of the keyboard. It should fill most of the preview.
5. Desk View shows the paper **upside down**. Press **R** twice. This is saved per camera.
6. Use even, bright light, and keep arms out of the frame.

## Step 7 — Verify (required)

Ask the human to press **SPACE** on one quiz sheet. Then open the newest file and look at it yourself:

```bash
ls -t "$(python3 -c 'import json;print(json.load(open("'$HOME'/Dev/doc-snap/config.json"))["out"])')" | head -1
```

Pass if **all** of these are true:
- The text is upright.
- The printed text and the handwriting are readable.
- The paper fills most of the image.

If it fails: blurry → wrong camera or too close; small → move the paper closer or change the tilt; dark → more light.

## Keys

| Key | Action |
|---|---|
| SPACE / ENTER / click green bar | Capture (click sound + white flash) |
| C | Next camera (re-scans the list; remembered) |
| R | Rotate 90° (remembered per camera) |
| G | Grayscale on/off |
| O | Open the output folder |
| Q / ESC | Quit |

Files are named `doc_YYYYMMDD_HHMMSS_mmm.jpg`, so they sort in capture order.

## `config.json` keys

`out`, `max_side`, `quality`, `prefix`, `gray`, `camera_name` (string), `rotate` (`{camera_name: quarter_turns}`).
Delete the file to reset everything.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `not authorized to capture video` | Launched from an agent shell or IDE | `open -a Terminal .../doc-snap.command`; human clicks OK; relaunch |
| Black window, "Starting camera..." stays | Camera busy, or a mode not supported | Close other camera apps (Zoom, FaceTime, Photo Booth); press C |
| Wrong camera opens | Saved `camera_name` | Press C, or delete `camera_name` from `config.json` |
| iPhone not listed | Continuity not active | Check Photo Booth → Camera menu; same Apple ID; Wi-Fi + Bluetooth; iPhone locked and still; press C to re-scan |
| Desk View shows the person, not the desk | Screen tilted too far back, or laptop on a lap | Tilt to about 100°, laptop on a table |
| Text upside down | Normal for Desk View | Press R twice |
| `ffmpeg: command not found` | Not installed | `brew install ffmpeg` |

## Committing changes

Use the human's normal git identity. Do not commit `config.json`, `.venv/`, `click.wav` or photos; they are git-ignored.
