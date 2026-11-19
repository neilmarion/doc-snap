#!/bin/bash
# Double-click in Finder to start. Extra args pass through, e.g. ./doc-snap.command --out ~/Desktop/quizzes
cd "$(dirname "$0")"
if ! command -v ffmpeg >/dev/null 2>&1; then
  for p in /opt/homebrew/bin /usr/local/bin; do [ -x "$p/ffmpeg" ] && export PATH="$p:$PATH"; done
fi
if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "ffmpeg is missing. Install it with:  brew install ffmpeg"; read -n1 -p "Press any key to close."; exit 1
fi
if [ ! -d .venv ]; then
  python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt || { echo "Install failed."; read -n1; exit 1; }
fi
exec .venv/bin/python doc_snap.py "$@"
