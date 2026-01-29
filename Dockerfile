FROM nvidia/cuda:12.4.1-cudnn-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive \
    PIP_NO_CACHE_DIR=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    git curl ca-certificates \
    python3 python3-pip python3-venv \
    ffmpeg \
    supervisor dumb-init \
 && rm -rf /var/lib/apt/lists/*

RUN python3 -m pip install --upgrade pip

# PyTorch (cu121 wheels are fine for A5000/A40)
RUN python3 -m pip install \
    torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

# JupyterLab + notebook deps
RUN python3 -m pip install jupyterlab
RUN python3 -m pip install -U requests ipywidgets jupyterlab_widgets

# Impact Pack deps
RUN python3 -m pip install piexif opencv-python-headless

# Segment Anything (Impact Pack uses this)
RUN python3 -m pip install git+https://github.com/facebookresearch/segment-anything.git

# DWpose deps
RUN python3 -m pip install onnxruntime-gpu --extra-index-url https://aiinfra.pkgs.visualstudio.com/PublicPackages/_packaging/onnxruntime-cuda-12/pypi/simple/

# FileBrowser (pinned binary install; avoids flaky get.sh in CI)
ARG FILEBROWSER_VERSION=2.27.0
RUN curl -fL "https://github.com/filebrowser/filebrowser/releases/download/v${FILEBROWSER_VERSION}/linux-amd64-filebrowser.tar.gz" \
    -o /tmp/filebrowser.tar.gz \
 && tar -xzf /tmp/filebrowser.tar.gz -C /usr/local/bin filebrowser \
 && chmod +x /usr/local/bin/filebrowser \
 && rm -f /tmp/filebrowser.tar.gz
 
# ---- ComfyUI baked into /opt so it isn't hidden by /workspace volume mounts ----
WORKDIR /opt
RUN git clone https://github.com/comfyanonymous/ComfyUI.git

WORKDIR /opt/ComfyUI
RUN python3 -m pip install -r requirements.txt

# ---- Bake custom nodes into the baked ComfyUI ----
WORKDIR /opt/ComfyUI/custom_nodes
RUN git clone https://github.com/ltdrdata/ComfyUI-Manager.git
RUN git clone https://github.com/Fannovel16/comfyui_controlnet_aux.git
RUN git clone https://github.com/cubiq/ComfyUI_IPAdapter_plus.git
RUN git clone https://github.com/ssitu/ComfyUI_UltimateSDUpscale.git
RUN git clone https://github.com/ltdrdata/ComfyUI-Impact-Pack.git
RUN git clone https://github.com/rgthree/rgthree-comfy.git

WORKDIR /opt/ComfyUI
RUN bash -lc 'for d in custom_nodes/*; do \
  if [ -f "$d/requirements.txt" ]; then \
    echo "Installing requirements for $d"; \
    python3 -m pip install -r "$d/requirements.txt" || true; \
  fi; \
done'

# ---- Notebook baked into /opt (not masked by /workspace) ----
RUN mkdir -p /opt/notebooks
COPY notebooks/model_downloader.ipynb /opt/notebooks/model_downloader.ipynb
COPY notebooks/model_downloader_app.py /opt/notebooks/model_downloader_app.py

# Supervisor + start
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf
COPY start.sh /start.sh
RUN chmod +x /start.sh

EXPOSE 8188 8888 8080

ENTRYPOINT ["dumb-init", "--"]
CMD ["/start.sh"]
