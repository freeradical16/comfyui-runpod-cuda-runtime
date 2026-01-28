#!/usr/bin/env bash
set -euo pipefail

# Ensure ComfyUI exists on the volume (if you’re using the /opt -> /workspace copy pattern)
if [ ! -f /workspace/ComfyUI/main.py ] && [ -f /opt/ComfyUI/main.py ]; then
  echo "[init] /workspace/ComfyUI missing; copying baked ComfyUI from /opt/ComfyUI..."
  rm -rf /workspace/ComfyUI
  cp -a /opt/ComfyUI /workspace/ComfyUI
fi

# Notebook: always refresh into /workspace so Jupyter never points at a missing file
mkdir -p /workspace/notebooks

# Notebook
if [ -f /opt/notebooks/model_downloader.ipynb ]; then
  cp -f /opt/notebooks/model_downloader.ipynb /workspace/notebooks/model_downloader.ipynb
  chmod 644 /workspace/notebooks/model_downloader.ipynb || true
  echo "[init] Refreshed model_downloader.ipynb -> /workspace/notebooks"
else
  echo "[init] WARNING: /opt/notebooks/model_downloader.ipynb not found"
fi

# App .py
if [ -f /opt/notebooks/model_downloader_app.py ]; then
  cp -f /opt/notebooks/model_downloader_app.py /workspace/notebooks/model_downloader_app.py
  chmod 644 /workspace/notebooks/model_downloader_app.py || true
  echo "[init] Refreshed model_downloader_app.py -> /workspace/notebooks"
else
  echo "[init] WARNING: /opt/notebooks/model_downloader_app.py not found"
fi

exec /usr/bin/supervisord -c /etc/supervisor/conf.d/supervisord.conf
