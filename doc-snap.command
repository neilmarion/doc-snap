#!/bin/bash
# Double-click in Finder to start. Extra args pass through, e.g. ./doc-snap.command --out ~/Desktop/quizzes
cd "$(dirname "$0")"
if [ ! -d .venv ]; then
  python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt
fi
exec .venv/bin/python doc_snap.py "$@"
