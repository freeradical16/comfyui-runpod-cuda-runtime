# ComfyUI RunPod Image (CUDA runtime) + JupyterLab + FileBrowser

This repo builds a Docker image for RunPod with:
- ComfyUI on port **8188**
- JupyterLab on port **8888**
- FileBrowser on port **8080**
- A baked-in notebook: **Model Downloader (URLs only)**

All services are managed by **supervisord** (single container, multiple services).

## What’s inside
- Base: `nvidia/cuda:12.4.1-cudnn-runtime-ubuntu22.04`
- PyTorch installed (CUDA wheels)
- ComfyUI installed

Custom nodes baked in:
- ComfyUI-Manager
- comfyui_controlnet_aux
- ComfyUI_IPAdapter_plus
- ComfyUI_UltimateSDUpscale
- ComfyUI-Impact-Pack
- rgthree-comfy

Notebook baked into the image:
- `/workspace/notebooks/model_downloader.ipynb`

## Ports
Expose these in your RunPod template/pod:
- **8188** = ComfyUI
- **8888** = JupyterLab
- **8080** = FileBrowser

## Environment variables
Recommended:
- `JUPYTER_TOKEN` = token for JupyterLab access (leave blank only if you accept it being open)
- `CIVITAI_TOKEN` = CivitAI API token (for downloads requiring auth)
- `HF_TOKEN` = Hugging Face token (only needed for gated/private downloads)

Optional:
- `FILEBROWSER_NOAUTH=1` = run FileBrowser without login

## Where to put models
Use a RunPod **volume** for models + outputs.

ComfyUI model folders:
- `/workspace/ComfyUI/models/checkpoints`
- `/workspace/ComfyUI/models/loras`
- `/workspace/ComfyUI/models/vae`
- `/workspace/ComfyUI/models/controlnet`
- `/workspace/ComfyUI/models/ipadapter`
- `/workspace/ComfyUI/models/text_encoders`
- `/workspace/ComfyUI/models/diffusion_models`
- `/workspace/ComfyUI/models/unet`

## Using the downloader notebook
Open JupyterLab (port 8888), then open:
- `/workspace/notebooks/model_downloader.ipynb`

It supports:
- Single URL downloads
- Batch URL downloads (one per line)
- Uses `CIVITAI_TOKEN` automatically for civitai.com URLs

## Build + publish
This repo is intended to be built by GitHub Actions and pushed to GHCR.

Resulting image name pattern:
- `ghcr.io/freeradical16/<repo-name>:latest`

Then set that image in your RunPod template.
