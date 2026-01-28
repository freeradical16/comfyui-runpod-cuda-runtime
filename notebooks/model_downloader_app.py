"""
Model Downloader App (URLs only)
- Single download + batch download
- Batch supports per-line folder override: "loras https://..."
- Resume support (.part files)
- Uses CIVITAI_TOKEN and HF_TOKEN env vars if set
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from urllib.parse import unquote

import requests
from tqdm.auto import tqdm

import ipywidgets as w
from IPython.display import display, clear_output


# ----------------------------
# Paths / Folder Map
# ----------------------------
COMFY = Path("/workspace/ComfyUI")
MODELS = COMFY / "models"

folders: dict[str, Path] = {
    "checkpoints": MODELS / "checkpoints",
    "loras": MODELS / "loras",
    "vae": MODELS / "vae",
    "controlnet": MODELS / "controlnet",
    "ipadapter": MODELS / "ipadapter",
    "clip_vision": MODELS / "clip_vision",
    "text_encoders": MODELS / "text_encoders",
    "diffusion_models": MODELS / "diffusion_models",
    "unet": MODELS / "unet",
}

for p in folders.values():
    p.mkdir(parents=True, exist_ok=True)


# ----------------------------
# Helpers
# ----------------------------
def _safe_filename(name: str) -> str:
    # Avoid path traversal + weird slashes
    name = name.replace("\\", "_").replace("/", "_").strip()
    # Some URLs produce absurd names; don't “fix” that here beyond path safety.
    return name or "download.bin"


def _filename_from_cd(cd: str | None) -> str | None:
    """
    Robust-ish Content-Disposition filename extraction:
    - filename*=UTF-8''...
    - filename="..."
    - filename=...
    """
    if not cd:
        return None

    # filename*=UTF-8''something
    m = re.search(r"filename\*\s*=\s*UTF-8''([^;]+)", cd, flags=re.IGNORECASE)
    if m:
        return Path(unquote(m.group(1).strip().strip('"'))).name

    # filename="something"
    m = re.search(r'filename\s*=\s*"([^"]+)"', cd, flags=re.IGNORECASE)
    if m:
        return Path(m.group(1)).name

    # filename=something
    m = re.search(r"filename\s*=\s*([^;]+)", cd, flags=re.IGNORECASE)
    if m:
        return Path(m.group(1).strip().strip('"')).name

    return None


def _headers_for_url(url: str) -> dict[str, str]:
    headers: dict[str, str] = {}

    civ = os.environ.get("CIVITAI_TOKEN", "").strip()
    if "civitai.com" in url and civ:
        headers["Authorization"] = f"Bearer {civ}"

    hf = os.environ.get("HF_TOKEN", "").strip()
    if ("huggingface.co" in url or "hf.co" in url) and hf:
        # This is safe to send; ignored by public endpoints, needed by gated models.
        headers["Authorization"] = f"Bearer {hf}"

    return headers


def download(
    url: str,
    folder_key: str,
    filename: str | None = None,
    overwrite: bool = False,
) -> Path:
    """
    Download URL into ComfyUI/models/<folder_key>.
    - Writes to <file>.part then renames
    - Supports resume if server supports Range
    """
    if folder_key not in folders:
        raise ValueError(f"folder_key must be one of: {list(folders.keys())}")

    dest_dir = folders[folder_key]
    dest_dir.mkdir(parents=True, exist_ok=True)

    headers = _headers_for_url(url)

    # Probe request: resolve final URL, sniff filename and size
    with requests.get(url, headers=headers, stream=True, allow_redirects=True, timeout=60) as r:
        r.raise_for_status()

        if not filename:
            filename = _filename_from_cd(r.headers.get("content-disposition"))

        if not filename:
            # Fallback: parse from URL
            filename = url.split("?")[0].rstrip("/").split("/")[-1] or "download.bin"

        filename = _safe_filename(filename)
        dest = dest_dir / filename
        tmp = dest.with_suffix(dest.suffix + ".part")

        if dest.exists() and not overwrite:
            return dest

        if dest.exists() and overwrite:
            dest.unlink(missing_ok=True)

        existing = tmp.stat().st_size if tmp.exists() else 0
        cl = r.headers.get("content-length")
        total = (int(cl) + existing) if (cl and existing) else (int(cl) if cl else None)

    # Resume if partial exists
    req_headers = dict(headers)
    mode = "wb"

    if existing > 0:
        req_headers["Range"] = f"bytes={existing}-"
        mode = "ab"

    with requests.get(url, headers=req_headers, stream=True, allow_redirects=True, timeout=60) as r2:
        # If server doesn't support Range, it might return 200 even though we asked for Range.
        # If we get 200 with existing bytes, restart clean.
        if existing > 0 and r2.status_code == 200:
            existing = 0
            mode = "wb"

        r2.raise_for_status()

        with open(tmp, mode) as f, tqdm(
            total=total,
            initial=existing,
            unit="B",
            unit_scale=True,
            desc=filename,
        ) as pbar:
            for chunk in r2.iter_content(chunk_size=1024 * 1024):
                if not chunk:
                    continue
                f.write(chunk)
                pbar.update(len(chunk))

    tmp.rename(dest)
    return dest


# ----------------------------
# Batch Parsing
# ----------------------------
def _parse_batch_lines(text: str) -> list[tuple[str | None, str]]:
    """
    Supports:
      - https://...                      -> (None, url)
      - loras https://...                -> (folder, url)
      - controlnet    https://...        -> (folder, url)
    """
    items: list[tuple[str | None, str]] = []
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue

        parts = s.split(None, 1)  # first whitespace
        if len(parts) == 2 and parts[0] in folders:
            items.append((parts[0], parts[1].strip()))
        else:
            items.append((None, s))
    return items


# ----------------------------
# UI
# ----------------------------
setup_out = w.Output()
single_out = w.Output()
batch_out = w.Output()

# Single controls
single_folder_dd = w.Dropdown(options=list(folders.keys()), value="checkpoints", description="Folder:")
single_overwrite_cb = w.Checkbox(value=False, description="Overwrite")
url_tb = w.Text(value="", placeholder="Paste URL…", description="URL:", layout=w.Layout(width="900px"))
name_tb = w.Text(value="", placeholder="Optional filename override", description="Name:", layout=w.Layout(width="900px"))
btn_single = w.Button(description="Download (Single)", button_style="success")

# Batch controls (independent)
batch_folder_dd = w.Dropdown(options=list(folders.keys()), value="checkpoints", description="Default:")
batch_overwrite_cb = w.Checkbox(value=False, description="Overwrite")
batch_tb = w.Textarea(
    value="",
    placeholder=(
        "One per line\n"
        "# comment lines ignored\n"
        "Optionally prefix with folder:\n"
        "loras https://...\n"
        "checkpoints https://...\n"
        "controlnet https://...\n"
    ),
    description="URLs:",
    layout=w.Layout(width="900px", height="200px"),
)
btn_batch = w.Button(description="Download (Batch)", button_style="success")

btn_setup = w.Button(description="Run Setup Check", button_style="info")


def _setup(_):
    with setup_out:
        clear_output(wait=True)
        print("ComfyUI:", COMFY)
        print("Models :", MODELS)
        print("CIVITAI_TOKEN set?", bool(os.environ.get("CIVITAI_TOKEN")))
        print("HF_TOKEN set?    ", bool(os.environ.get("HF_TOKEN")))
        print("\nFolders:")
        for k, p in folders.items():
            print(f"  {k:16s} -> {p}")


def _do_single(_):
    with single_out:
        clear_output(wait=True)
        url = url_tb.value.strip()
        if not url:
            print("Paste a URL first.")
            return

        out_path = download(
            url=url,
            folder_key=single_folder_dd.value,
            filename=(name_tb.value.strip() or None),
            overwrite=single_overwrite_cb.value,
        )
        print("Saved:", out_path)


def _do_batch(_):
    with batch_out:
        clear_output(wait=True)

        parsed = _parse_batch_lines(batch_tb.value)
        if not parsed:
            print("Paste at least one URL.")
            return

        default_folder = batch_folder_dd.value
        ow = batch_overwrite_cb.value

        fails = 0
        for i, (fk, url) in enumerate(parsed, 1):
            folder_key = fk or default_folder
            try:
                print(f"[{i}/{len(parsed)}] ({folder_key}) {url}")
                out_path = download(url=url, folder_key=folder_key, overwrite=ow)
                print("  Saved:", out_path)
            except Exception as e:
                fails += 1
                print("  FAILED:", e)

        print("\nDone. Failures:", fails)


btn_setup.on_click(_setup)
btn_single.on_click(_do_single)
btn_batch.on_click(_do_batch)

tabs = w.Tab(children=[
    w.VBox([w.HBox([btn_setup]), setup_out]),
    w.VBox([w.HBox([single_folder_dd, single_overwrite_cb]), url_tb, name_tb, btn_single, single_out]),
    w.VBox([w.HBox([batch_folder_dd, batch_overwrite_cb]), batch_tb, btn_batch, batch_out]),
])
tabs.set_title(0, "Setup")
tabs.set_title(1, "Single")
tabs.set_title(2, "Batch")

display(tabs)
