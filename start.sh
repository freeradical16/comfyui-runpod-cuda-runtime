#!/usr/bin/env bash
set -euo pipefail

# ---- Notebook fix for /workspace volume mounts ----
mkdir -p /workspace/notebooks
if [ ! -f /workspace/notebooks/model_downloader.ipynb ] && [ -f /opt/notebooks/model_downloader.ipynb ]; then
  cp -f /opt/notebooks/model_downloader.ipynb /workspace/notebooks/model_downloader.ipynb
  echo "[init] Copied model_downloader.ipynb -> /workspace/notebooks"
fi

# Supervisor runs ComfyUI + JupyterLab + FileBrowser
exec /usr/bin/supervisord -c /etc/supervisor/conf.d/supervisord.conf
