# ComfyUI RunPod Image (CUDA runtime) + JupyterLab + FileBrowser

This repo builds a Docker image for RunPod with:
- ComfyUI on port **8188**
- JupyterLab on port **8888** (NO AUTH)
- FileBrowser on port **8080** (NO AUTH)
- A baked-in notebook: **Model Downloader (URLs only)**

All services are managed by **supervisord**.

## Notebook fix (important)
If you mount a RunPod volume at `/workspace`, it hides files baked into `/workspace` at image build time.
So the notebook is baked into:
- `/opt/notebooks/model_downloader.ipynb`

On container start, it is copied into:
- `/workspace/notebooks/model_downloader.ipynb`
(if missing)

## Ports
Expose these in your RunPod template/pod:
- **8188** = ComfyUI
- **8888** = JupyterLab
- **8080** = FileBrowser

## Environment variables
Optional:
- `CIVITAI_TOKEN` = CivitAI API token (for downloads requiring auth)
- `HF_TOKEN` = Hugging Face token (only needed for gated/private downloads)

## Custom nodes baked in
- ComfyUI-Manager
- comfyui_controlnet_aux
- ComfyUI_IPAdapter_plus
- ComfyUI_UltimateSDUpscale
- ComfyUI-Impact-Pack
- rgthree-comfy
