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
import time
from pathlib import Path
from urllib.parse import unquote

import requests

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

    m = re.search(r"filename\*\s*=\s*UTF-8''([^;]+)", cd, flags=re.IGNORECASE)
    if m:
        return Path(unquote(m.group(1).strip().strip('"'))).name

    m = re.search(r'filename\s*=\s*"([^"]+)"', cd, flags=re.IGNORECASE)
    if m:
        return Path(m.group(1)).name

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
        headers["Authorization"] = f"Bearer {hf}"

    return headers


def _fmt_bytes(n: int | None) -> str:
    if n is None:
        return "?"
    n = int(n)
    units = ["B", "KB", "MB", "GB", "TB"]
    f = float(n)
    for u in units:
        if f < 1024.0 or u == units[-1]:
            return f"{f:.1f} {u}" if u != "B" else f"{int(f)} B"
        f /= 1024.0
    return f"{f:.1f} TB"


# ----------------------------
# Downloader (with optional UI callback)
# ----------------------------
def download(
    url: str,
    folder_key: str,
    filename: str | None = None,
    overwrite: bool = False,
    progress_cb=None,  # callable(downloaded:int, total:int|None, filename:str, phase:str)
) -> Path:
    """
    Download URL into ComfyUI/models/<folder_key>.
    - Writes to <file>.part then renames
    - Supports resume if server supports Range
    - If progress_cb provided, updates via callback (stable in Jupyter widgets)
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
            filename = url.split("?")[0].rstrip("/").split("/")[-1] or "download.bin"

        filename = _safe_filename(filename)
        dest = dest_dir / filename
        tmp = dest.with_suffix(dest.suffix + ".part")

        if dest.exists() and not overwrite:
            if progress_cb:
                progress_cb(dest.stat().st_size, dest.stat().st_size, filename, "skipped")
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

    if progress_cb:
        progress_cb(existing, total, filename, "start")

    with requests.get(url, headers=req_headers, stream=True, allow_redirects=True, timeout=60) as r2:
        # If server doesn't support Range, it might return 200 even though we asked for Range.
        # If we get 200 with existing bytes, restart clean.
        if existing > 0 and r2.status_code == 200:
            existing = 0
            mode = "wb"
            if progress_cb:
                progress_cb(existing, total, filename, "restart")

        r2.raise_for_status()

        wrote = existing
        last_ui = 0.0

        with open(tmp, mode) as f:
            for chunk in r2.iter_content(chunk_size=1024 * 1024):
                if not chunk:
                    continue
                f.write(chunk)
                wrote += len(chunk)

                if progress_cb:
                    now = time.time()
                    # throttle UI updates a bit (smoother / less spammy)
                    if (now - last_ui) >= 0.15:
                        progress_cb(wrote, total, filename, "downloading")
                        last_ui = now

    tmp.rename(dest)
    if progress_cb:
        progress_cb(dest.stat().st_size, dest.stat().st_size, filename, "done")
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
        parts = s.split(None, 1)
        if len(parts) == 2 and parts[0] in folders:
            items.append((parts[0], parts[1].strip()))
        else:
            items.append((None, s))
    return items


# ----------------------------
# UI (persistent widgets; no “progress disappears”)
# ----------------------------
setup_out = w.Output()

# ---- Single widgets
single_folder_dd = w.Dropdown(options=list(folders.keys()), value="checkpoints", description="Folder:")
single_overwrite_cb = w.Checkbox(value=False, description="Overwrite")
url_tb = w.Text(value="", placeholder="Paste URL…", description="URL:", layout=w.Layout(width="900px"))
name_tb = w.Text(value="", placeholder="Optional filename override", description="Name:", layout=w.Layout(width="900px"))
btn_single = w.Button(description="Download (Single)", button_style="success")

single_status = w.Label(value="Idle")
single_pbar = w.IntProgress(value=0, min=0, max=100, description="0%")
single_bytes = w.Label(value="")
single_log = w.Textarea(value="", layout=w.Layout(width="900px", height="160px"))

# ---- Batch widgets
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

batch_status = w.Label(value="Idle")
batch_pbar = w.IntProgress(value=0, min=0, max=100, description="0%")
batch_bytes = w.Label(value="")
batch_log = w.Textarea(value="", layout=w.Layout(width="900px", height="200px"))

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


def _make_progress_cb(status_lbl: w.Label, pbar: w.IntProgress, bytes_lbl: w.Label, log: w.Textarea):
    last_pct = {"v": -1}

    def cb(downloaded: int, total: int | None, filename: str, phase: str):
        if phase == "skipped":
            status_lbl.value = f"Skipped (already exists): {filename}"
            pbar.max = 100
            pbar.value = 100
            pbar.description = "100%"
            bytes_lbl.value = ""
            log.value += f"[SKIP] {filename}\n"
            return

        if phase in ("start", "restart"):
            status_lbl.value = f"Downloading: {filename}"
            last_pct["v"] = -1
            if total and total > 0:
                pbar.max = int(total)
                pbar.value = int(downloaded)
                pct = int((downloaded / total) * 100)
                pbar.description = f"{pct}%"
                bytes_lbl.value = f"{_fmt_bytes(downloaded)} / {_fmt_bytes(total)}"
            else:
                pbar.max = 100
                pbar.value = 0
                pbar.description = "..."
                bytes_lbl.value = f"{_fmt_bytes(downloaded)} / ?"
            if phase == "restart":
                log.value += "[INFO] Server ignored Range; restarting download.\n"
            return

        if phase == "downloading":
            if total and total > 0:
                pbar.max = int(total)
                pbar.value = int(min(downloaded, total))
                pct = int((downloaded / total) * 100)
                if pct != last_pct["v"]:
                    pbar.description = f"{pct}%"
                    last_pct["v"] = pct
                bytes_lbl.value = f"{_fmt_bytes(downloaded)} / {_fmt_bytes(total)}"
            else:
                # unknown total: show activity
                pbar.max = 100
                pbar.value = (pbar.value + 1) % 100
                pbar.description = "..."
                bytes_lbl.value = f"{_fmt_bytes(downloaded)} / ?"
            return

        if phase == "done":
            status_lbl.value = f"Saved: {filename}"
            pbar.max = 100
            pbar.value = 100
            pbar.description = "100%"
            bytes_lbl.value = ""
            log.value += f"[OK] {filename}\n"
            return

    return cb


def _do_single(_):
    url = url_tb.value.strip()
    if not url:
        single_status.value = "Paste a URL first."
        return

    btn_single.disabled = True
    single_log.value = ""
    single_pbar.max = 100
    single_pbar.value = 0
    single_pbar.description = "0%"
    single_bytes.value = ""
    single_status.value = "Starting…"

    cb = _make_progress_cb(single_status, single_pbar, single_bytes, single_log)

    try:
        out_path = download(
            url=url,
            folder_key=single_folder_dd.value,
            filename=(name_tb.value.strip() or None),
            overwrite=single_overwrite_cb.value,
            progress_cb=cb,
        )
        single_log.value += f"Saved path: {out_path}\n"
    except Exception as e:
        single_status.value = "FAILED"
        single_log.value += f"[FAILED] {e}\n"
    finally:
        btn_single.disabled = False


def _do_batch(_):
    parsed = _parse_batch_lines(batch_tb.value)
    if not parsed:
        batch_status.value = "Paste at least one URL."
        return

    btn_batch.disabled = True
    batch_log.value = ""
    batch_pbar.max = 100
    batch_pbar.value = 0
    batch_pbar.description = "0%"
    batch_bytes.value = ""
    batch_status.value = "Starting…"

    ow = batch_overwrite_cb.value
    default_folder = batch_folder_dd.value

    fails = 0
    fail_list = []

    # retry settings (tweak as you like)
    MAX_RETRIES = 2
    RETRY_SLEEP_SEC = 2

    try:
        total_items = len(parsed)

        for i, (fk, url) in enumerate(parsed, 1):
            folder_key = fk or default_folder
            url = url.strip()

            batch_status.value = f"[{i}/{total_items}] ({folder_key})"
            batch_log.value += f"[{i}/{total_items}] ({folder_key}) {url}\n"

            cb = _make_progress_cb(batch_status, batch_pbar, batch_bytes, batch_log)

            success = False
            last_err = None

            for attempt in range(1, MAX_RETRIES + 2):  # e.g. 1..3 if MAX_RETRIES=2
                try:
                    if attempt > 1:
                        batch_log.value += f"  retry {attempt-1}/{MAX_RETRIES}…\n"

                    out_path = download(
                        url=url,
                        folder_key=folder_key,
                        overwrite=ow,
                        progress_cb=cb,
                    )
                    batch_log.value += f"Saved path: {out_path}\n"
                    success = True
                    break

                except Exception as e:
                    last_err = e
                    # log and retry
                    batch_log.value += f"  [FAILED attempt {attempt}] {e}\n"
                    if attempt <= MAX_RETRIES:
                        time.sleep(RETRY_SLEEP_SEC)

            if not success:
                fails += 1
                fail_list.append((folder_key, url, str(last_err)))
                batch_log.value += f"[GIVE UP] {url}\n\n"

        batch_status.value = f"Done. Failures: {fails}"
        batch_pbar.max = 100
        batch_pbar.value = 100
        batch_pbar.description = "100%"
        batch_bytes.value = ""

        if fails:
            batch_log.value += "\n=== FAILURES SUMMARY ===\n"
            for (fk, u, err) in fail_list:
                batch_log.value += f"- ({fk}) {u}\n  -> {err}\n"

    finally:
        btn_batch.disabled = False


btn_setup.on_click(_setup)
btn_single.on_click(_do_single)
btn_batch.on_click(_do_batch)

tabs = w.Tab(children=[
    w.VBox([w.HBox([btn_setup]), setup_out]),
    w.VBox([
        w.HBox([single_folder_dd, single_overwrite_cb]),
        url_tb, name_tb, btn_single,
        single_status, single_pbar, single_bytes,
        single_log
    ]),
    w.VBox([
        w.HBox([batch_folder_dd, batch_overwrite_cb]),
        batch_tb, btn_batch,
        batch_status, batch_pbar, batch_bytes,
        batch_log
    ]),
])

tabs.set_title(0, "Setup")
tabs.set_title(1, "Single")
tabs.set_title(2, "Batch")

display(tabs)
