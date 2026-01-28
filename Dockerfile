FROM nvidia/cuda:12.4.1-cudnn-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive \
    PIP_NO_CACHE_DIR=1 \
    PYTHONUNBUFFERED=1

# OS deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    git curl ca-certificates \
    python3 python3-pip python3-venv \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m pip install --upgrade pip

# PyTorch (works fine on A5000/A40; cu121 wheels are the common “easy mode”)
RUN python3 -m pip install \
    torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

# JupyterLab (file browser + terminal)
RUN python3 -m pip install jupyterlab

# Notebook deps 
RUN python3 -m pip install -U requests tqdm ipywidgets jupyterlab_widgets

# ComfyUI
WORKDIR /workspace
RUN git clone https://github.com/comfyanonymous/ComfyUI.git

WORKDIR /workspace/ComfyUI
RUN python3 -m pip install -r requirements.txt

# ---- Bake custom nodes ----
WORKDIR /workspace/ComfyUI/custom_nodes

# Manager
RUN git clone https://github.com/ltdrdata/ComfyUI-Manager.git

# ControlNet preprocessors (DWpose, depth, etc.)
RUN git clone https://github.com/Fannovel16/comfyui_controlnet_aux.git

# IP-Adapter
RUN git clone https://github.com/cubiq/ComfyUI_IPAdapter_plus.git

# Ultimate SD Upscale
RUN git clone https://github.com/ssitu/ComfyUI_UltimateSDUpscale.git

# Impact Pack (FaceDetailer, detectors, etc.)
RUN git clone https://github.com/ltdrdata/ComfyUI-Impact-Pack.git

# ---- Install custom node requirements (best-effort) ----
WORKDIR /workspace/ComfyUI
RUN bash -lc 'for d in custom_nodes/*; do \
  if [ -f "$d/requirements.txt" ]; then \
    echo "Installing requirements for $d"; \
    python3 -m pip install -r "$d/requirements.txt" || true; \
  fi; \
done'

# Ports: ComfyUI + JupyterLab
EXPOSE 8188 8888

COPY start.sh /start.sh
RUN chmod +x /start.sh

CMD ["/start.sh"]
