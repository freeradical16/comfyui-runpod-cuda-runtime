# ComfyUI RunPod Image (CUDA runtime) + JupyterLab + FileBrowser

This repo builds a Docker image for RunPod with:
- ComfyUI on port **8188**
- JupyterLab on port **8888** (NO AUTH)
- FileBrowser on port **8080** (NO AUTH)
- A baked-in downloader:
  - **Model Downloader notebook** (`model_downloader.ipynb`)
  - **Model Downloader app script** (`model_downloader_app.py`)

All services are managed by **supervisord**.

---

## RunPod Template Checklist (so it actually works first boot)

### 1) Image
- Use the Docker image built from this repo (your published tag).

### 2) Ports to expose
Expose these as HTTP ports in the RunPod template:
- **8188** → ComfyUI
- **8888** → JupyterLab (no auth)
- **8080** → FileBrowser (no auth)

### 3) Volume / persistence
Recommended:
- Mount a persistent volume to: **`/workspace`**

Why:
- `/workspace` is where ComfyUI runs and where models get downloaded.
- Anything under `/workspace` persists between pod runs.

Important:
- Mounting a volume at `/workspace` hides files baked into the image under `/workspace`.
- That’s why notebooks/scripts are baked into `/opt/notebooks` and copied into `/workspace/notebooks` on startup.

### 4) Environment variables (optional, for downloads)
Add these to the template **only if you need them**:
- `CIVITAI_TOKEN` = for Civitai models that require auth
- `HF_TOKEN` = for gated/private Hugging Face downloads

### 5) GPU selection (practical guidance)
- **A5000 / A40**: solid value for SDXL/ControlNet/IPAdapter workflows.
- If you start using very large FLUX/Z-image workflows + multiple controlnets + high-res upscales, you’ll want more VRAM.

### 6) Quick “is it alive?” smoke test
After the pod starts:
- Open **ComfyUI** (8188) and confirm it loads the UI.
- Open **FileBrowser** (8080) and confirm you can browse `/workspace`.
- Open **JupyterLab** (8888) and confirm terminals/notebooks open.

---

## Model Downloader (Notebook + App)

### Why it’s baked into `/opt`
If you mount a RunPod volume at `/workspace`, it hides files baked into `/workspace` at image build time.
So the downloader is baked into:
- `/opt/notebooks/model_downloader.ipynb`
- `/opt/notebooks/model_downloader_app.py`

On container start, both are copied into:
- `/workspace/notebooks/model_downloader.ipynb`
- `/workspace/notebooks/model_downloader_app.py`

This makes them visible in JupyterLab under `/workspace/notebooks`.

> Note: the startup script currently uses `cp -f` (overwrite) when copying from `/opt` to `/workspace`.
> If you want your edits in `/workspace/notebooks` to persist across restarts without being overwritten, change `cp -f` to `cp -n` in `start.sh`.

### Notebook usage
Open in JupyterLab:
- `/workspace/notebooks/model_downloader.ipynb`

Features:
- **Single download**: URL + folder + optional filename override.
- **Batch download**: paste multiple URLs.
- Batch supports optional filename override per-line using:
  - `URL | filename.safetensors`

---

## Ports (set these on your RunPod template)
Expose these in your RunPod template/pod:
- **8188** = ComfyUI
- **8888** = JupyterLab
- **8080** = FileBrowser

---

## Environment variables (optional)
- `CIVITAI_TOKEN` = CivitAI API token (for downloads requiring auth)
- `HF_TOKEN` = Hugging Face token (only needed for gated/private downloads)

---

## Custom nodes baked in
- ComfyUI-Manager
- comfyui_controlnet_aux
- ComfyUI_IPAdapter_plus
- ComfyUI_UltimateSDUpscale
- ComfyUI-Impact-Pack
- rgthree-comfy

---

## Notes
- JupyterLab and FileBrowser are intentionally configured with **no authentication**. You’re accepting that risk.
- If you run into “destination name is too long” with CLI tools, prefer using the downloader with an explicit filename override.
