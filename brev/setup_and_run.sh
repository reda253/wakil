#!/usr/bin/env bash
set -e

echo "=== [Wakil GPU] Setting up faster-whisper on CUDA ==="
pip install --upgrade pip
pip install faster-whisper fastapi uvicorn python-multipart

echo "=== [Wakil GPU] Stopping any previous server ==="
pkill -f "whisper_server" || true

export WHISPER_TOKEN="${WHISPER_TOKEN:-db7e654c0d28cfa488404ab7a88730a0}"
echo "=== [Wakil GPU] Launching whisper_server.py on port 8000 ==="
nohup python3 -u ~/whisper_server.py > ~/whisper.log 2>&1 &

echo "Waiting for Whisper server to spin up..."
for i in {1..15}; do
    if curl -s http://localhost:8000/health | grep -q "ok"; then
        echo "=== [Wakil GPU] SUCCESS: Whisper GPU Server is healthy and running on port 8000! ==="
        exit 0
    fi
    sleep 2
done

echo "Server starting up in background, check ~/whisper.log for details."
