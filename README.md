# doc-snap

Very fast, one-press webcam capture of documents (quiz sheets, forms, notes) to feed to Claude or any LLM.
Low-res JPEGs on purpose: small files, still readable.

## Start

```bash
./doc-snap.command --out ~/Documents/quiz-photos
```

Or double-click `doc-snap.command` in Finder. The folder is remembered for next time.
First run makes a `.venv` and installs OpenCV. macOS asks for camera access once.

## Keys

| Key | Action |
|---|---|
| SPACE / ENTER / click green bar | Capture (click sound + white flash) |
| C | Switch camera |
| G | Toggle grayscale |
| O | Open output folder |
| Q / ESC | Quit |

## Options

| Flag | Default | Meaning |
|---|---|---|
| `--out DIR` | `~/Pictures/doc-snap` | Save folder |
| `--camera N` | auto (Logitech/Brio by name) | Camera index (order printed at start) |
| `--max-side PX` | 1920 | Longest image side |
| `--quality Q` | 70 | JPEG quality |
| `--prefix NAME` | `doc` | File name prefix |
| `--gray` | off | Save grayscale |

Files are named `doc_YYYYMMDD_HHMMSS_mmm.jpg` so they sort in capture order.
