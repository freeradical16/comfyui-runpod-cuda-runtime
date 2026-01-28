#!/usr/bin/env bash
set -e

# JupyterLab
jupyter lab \
  --ip 0.0.0.0 --port 8888 \
  --no-browser --allow-root \
  --ServerApp.token="${JUPYTER_TOKEN:-}" \
  --ServerApp.password='' &

# ComfyUI
cd /workspace/ComfyUI
python3 main.py --listen 0.0.0.0 --port 8188
