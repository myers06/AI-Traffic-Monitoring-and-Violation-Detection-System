import json
import re
import shutil
import tempfile
import threading
from collections import Counter
from pathlib import Path

from fast_alpr import ALPR
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.config import ROOT, load_config
from app.database import (
    clear_plates,
    clear_violations,
    get_all_violations,
    get_plates,
)
from app.pipeline import ViolationPipeline

app = FastAPI(title="Traffic Violation Detection")

_cfg = load_config()
OUT_DIR = Path(_cfg["output"]["dir"])
OUT_DIR.mkdir(parents=True, exist_ok=True)
(OUT_DIR / "plates").mkdir(exist_ok=True)
LOG_PATH = OUT_DIR / "violations.jsonl"

VIDEO_DIR = ROOT / "videos"
UPLOAD_DIR = VIDEO_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
VIDEO_EXTS = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v"}

app.mount("/evidence", StaticFiles(directory=str(OUT_DIR)), name="evidence")

_pipeline: ViolationPipeline | None = None
_lock = threading.Lock()  # tracker state is shared, so one run at a time
_job = {
    "state": "idle",
    "source": None,
    "video": None,
    "count": 0,
    "progress": 0,
    "error": None,
}


class AnalyzeRequest(BaseModel):
    source: str  # path to a video file on the server, e.g. videos/clip.mp4


# -- helpers ------------------------------------------------------------------
def get_pipeline() -> ViolationPipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = ViolationPipeline(_cfg)
    return _pipeline


def rel(path: Path) -> str:
    """Path as shown in the dashboard, relative to the project root."""
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def resolve_video(source: str) -> Path:
    src = Path(source)
    if not src.is_absolute():
        src = ROOT / src
    if not src.is_file():
        raise HTTPException(404, f"Video not found: {source}")
    return src


def read_violations(type_: str | None = None) -> list[dict]:
    if not LOG_PATH.exists():
        return []
    rows = []
    for line in LOG_PATH.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        row["image_url"] = f"/evidence/{row['image']}" if row.get("image") else None
        rows.append(row)
    if type_:
        rows = [r for r in rows if r["type"] == type_]
    return rows[::-1]  # newest first


def _run_job(src: Path, label: str) -> None:
    try:
        with _lock:
            clear_plates(label)  # re-analysing a video replaces its plate list
            records = get_pipeline().run(
                str(src),
                video_label=label,
                progress=lambda p: _job.update(progress=round(p * 100)),
            )
        _job.update(state="done", count=len(records), progress=100, error=None)
    except Exception as e:  # shown in the dashboard
        _job.update(state="error", error=str(e))


def start_job(src: Path) -> dict:
    if _job["state"] == "running":
        raise HTTPException(409, "An analysis is already running")
    label = rel(src)
    _job.update(state="running", source=str(src), video=label,
                count=0, progress=0, error=None)
    threading.Thread(target=_run_job, args=(src, label), daemon=True).start()
    return {"started": True, "video": label}


# -- basic routes -------------------------------------------------------------
@app.get("/", include_in_schema=False)
def root():
    return {"message": "API running. Open the dashboard at http://localhost:3000"}


@app.get("/health")
def health():
    return {"status": "ok"}


# -- videos -------------------------------------------------------------------
@app.get("/api/videos")
def list_videos():
    """Every video in the project's videos/ folder, newest first."""
    files = [
        p for p in VIDEO_DIR.rglob("*")
        if p.is_file() and p.suffix.lower() in VIDEO_EXTS
    ]
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return [
        {
            "path": rel(p),
            "name": p.name,
            "size_mb": round(p.stat().st_size / 1_048_576, 1),
            "uploaded": UPLOAD_DIR in p.parents,
        }
        for p in files
    ]


@app.post("/api/videos/upload", status_code=201)
def upload_video(file: UploadFile = File(...), analyze: bool = True):
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in VIDEO_EXTS:
        raise HTTPException(
            400, "Upload a video file: MP4, MOV, AVI, MKV, WEBM or M4V."
        )
    if analyze and _job["state"] == "running":
        raise HTTPException(409, "Wait for the running analysis to finish")

    stem = re.sub(r"[^A-Za-z0-9_-]+", "_", Path(file.filename).stem).strip("_")
    stem = stem[:60] or "video"
    dest = UPLOAD_DIR / f"{stem}{suffix}"
    n = 1
    while dest.exists():
        dest = UPLOAD_DIR / f"{stem}_{n}{suffix}"
        n += 1

    try:
        with open(dest, "wb") as out:
            shutil.copyfileobj(file.file, out, length=1024 * 1024)
    except Exception as exc:
        dest.unlink(missing_ok=True)
        raise HTTPException(500, f"Upload failed: {exc}") from exc
    finally:
        file.file.close()

    if dest.stat().st_size == 0:
        dest.unlink(missing_ok=True)
        raise HTTPException(400, "The uploaded video is empty.")

    result = {"path": rel(dest), "name": dest.name}
    if analyze:
        result.update(start_job(dest))
    return result


@app.get("/api/video")
def get_video(path: str = "videos/17022934_4096_2160_60fps.mp4"):
    """Stream a video so the dashboard can play it."""
    src = resolve_video(path)
    if VIDEO_DIR.resolve() not in src.resolve().parents:
        raise HTTPException(403, "Only videos in the videos folder can be played")
    return FileResponse(src, media_type="video/mp4", filename=src.name)


# -- analysis -----------------------------------------------------------------
@app.post("/api/analyze", status_code=202)
def analyze_async(req: AnalyzeRequest):
    return start_job(resolve_video(req.source))


@app.get("/api/status")
def status():
    return _job


@app.get("/api/plates")
def plates(video: str | None = None):
    rows = get_plates(video)
    for r in rows:
        r["image_url"] = f"/evidence/{r['image']}" if r.get("image") else None
    return rows


@app.get("/api/violations")
def api_violations(type: str | None = None):
    return read_violations(type)


@app.get("/api/database-violations")
def database_violations():
    return get_all_violations()


@app.get("/api/stats")
def stats():
    rows = read_violations()
    return {"total": len(rows), "by_type": dict(Counter(r["type"] for r in rows))}


@app.post("/api/clear")
def clear():
    if _job["state"] == "running":
        raise HTTPException(409, "Wait for the running analysis to finish")
    for f in OUT_DIR.glob("*.jpg"):
        f.unlink(missing_ok=True)
    for f in (OUT_DIR / "plates").glob("*.jpg"):
        f.unlink(missing_ok=True)
    LOG_PATH.unlink(missing_ok=True)
    clear_violations()
    clear_plates()
    return {"cleared": True}


# -- photo number plate recognition -------------------------------------------
_photo_alpr = None


def get_photo_alpr():
    global _photo_alpr
    if _photo_alpr is None:
        _photo_alpr = ALPR(ocr_model="cct-xs-v2-global-model")
    return _photo_alpr


@app.post("/api/recognize-photo")
async def recognize_photo(file: UploadFile = File(...)):
    if file.content_type not in {"image/jpeg", "image/png"}:
        raise HTTPException(400, "Please upload a JPG or PNG image.")

    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(400, "The uploaded image is empty.")
    if len(image_bytes) > 15 * 1024 * 1024:
        raise HTTPException(413, "Image is too large. Maximum size is 15 MB.")

    suffix = ".png" if file.content_type == "image/png" else ".jpg"

    try:
        with tempfile.NamedTemporaryFile(suffix=suffix) as temp_file:
            temp_file.write(image_bytes)
            temp_file.flush()
            results = get_photo_alpr().predict(temp_file.name)

        plates_found = []
        for result in results:
            box = result.detection.bounding_box
            text = (result.ocr.text if result.ocr else "") or ""
            plates_found.append({
                "text": text.strip() or None,
                "detection_confidence": round(float(result.detection.confidence), 3),
                "box": {
                    "x1": int(box.x1), "y1": int(box.y1),
                    "x2": int(box.x2), "y2": int(box.y2),
                },
            })

        return {
            "filename": file.filename,
            "plate_count": len(plates_found),
            "plates": plates_found,
            "message": (
                "Recognition complete."
                if any(p["text"] for p in plates_found)
                else "No readable plate text found."
            ),
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, f"Photo recognition failed: {exc}") from exc
