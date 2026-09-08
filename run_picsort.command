#!/bin/bash
# Double-click this file in Finder to start PicSort on macOS.
cd "$(dirname "$0")" || exit 1

if [ -x ".venv/bin/python" ]; then
    PYTHON=".venv/bin/python"
else
    PYTHON="python3"
fi

if ! "$PYTHON" -c "import tkinter" 2>/dev/null; then
    echo "This Python has no Tkinter. Install Python from https://www.python.org/downloads/macos/"
    echo "or run: brew install python-tk"
    read -r -p "Press Enter to close."
    exit 1
fi

if ! "$PYTHON" -c "import PIL, imagehash, numpy, send2trash" 2>/dev/null; then
    echo "Installing dependencies…"
    "$PYTHON" -m pip install --user -r requirements.txt || "$PYTHON" -m pip install -r requirements.txt
fi

exec "$PYTHON" picsort.py
