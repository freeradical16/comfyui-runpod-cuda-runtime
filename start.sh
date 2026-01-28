#!/usr/bin/env bash
set -e

# Supervisor runs ComfyUI + JupyterLab + FileBrowser
exec /usr/bin/supervisord -c /etc/supervisor/conf.d/supervisord.conf
