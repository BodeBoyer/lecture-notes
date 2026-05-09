#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "Creating virtual environment..."
python3 -m venv .venv

echo "Installing dependencies (mlx-whisper will download ~150MB model on first run)..."
.venv/bin/pip install --upgrade pip -q
.venv/bin/pip install -r requirements.txt -q

if [ ! -f ".env" ]; then
    cp .env.example .env
    echo ""
    echo "Created .env — add your Anthropic API key:"
    echo "  echo 'ANTHROPIC_API_KEY=sk-ant-...' >> $SCRIPT_DIR/.env"
fi

echo ""
echo "Setup complete. Usage:"
echo "  $SCRIPT_DIR/.venv/bin/python $SCRIPT_DIR/notes.py <recording.m4a> \"COURSE NAME\""
echo ""
echo "For video files (mp4, mov, etc), also run: brew install ffmpeg"
