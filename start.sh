#!/usr/bin/env bash
set -euo pipefail

# If /workspace is a mounted volume, it may be empty and hide baked files.
# Copy ComfyUI into the volume the first time (or if it's missing).
if [ ! -f /workspace/ComfyUI/main.py ]; then
  echo "[init] /workspace/ComfyUI missing; copying baked ComfyUI from /opt/ComfyUI..."
  rm -rf /workspace/ComfyUI
  cp -a /opt/ComfyUI /workspace/ComfyUI
  echo "[init] Copied ComfyUI -> /workspace/ComfyUI"
fi

# Notebook fix
mkdir -p /workspace/notebooks
if [ ! -f /workspace/notebooks/model_downloader.ipynb ] && [ -f /opt/notebooks/model_downloader.ipynb ]; then
  cp -f /opt/notebooks/model_downloader.ipynb /workspace/notebooks/model_downloader.ipynb
  echo "[init] Copied model_downloader.ipynb -> /workspace/notebooks"
fi

exec /usr/bin/supervisord -c /etc/supervisor/conf.d/supervisord.conf
