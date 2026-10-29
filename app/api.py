import json
import threading
from collections import Counter
from pathlib import Path

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import tempfile
from fast_alpr import ALPR
from app.config import ROOT, load_config
from app.pipeline import ViolationPipeline
from app.database import get_all_violations


app = FastAPI(title="Traffic Violation Detection")

_cfg = load_config()
OUT_DIR = Path(_cfg["output"]["dir"])
OUT_DIR.mkdir(parents=True, exist_ok=True)
LOG_PATH = OUT_DIR / "violations.jsonl"

app.mount("/evidence", StaticFiles(directory=str(OUT_DIR)), name="evidence")
VIDEO_PATH = ROOT / "videos" / "17022934_4096_2160_60fps.mp4"

@app.get("/api/video")
def get_video():
    if not VIDEO_PATH.is_file():
        raise HTTPException(404, "Traffic video not found")
    return FileResponse(
        VIDEO_PATH,
        media_type="video/mp4",
        filename=VIDEO_PATH.name,
    )

_pipeline: ViolationPipeline | None = None
_lock = threading.Lock()  # tracker state is shared, so one run at a time
_job = {"state": "idle", "source": None, "count": 0, "error": None}


class AnalyzeRequest(BaseModel):
    source: str  # path to a video file on the server


# -- helpers ----------------------------------------------------------------
def get_pipeline() -> ViolationPipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = ViolationPipeline(_cfg)
    return _pipeline


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


def _run_job(source: str) -> None:
    try:
        with _lock:
            records = get_pipeline().run(source)
        _job.update(state="done", count=len(records), error=None)
    except Exception as e:  # shown in the dashboard
        _job.update(state="error", error=str(e))


# -- basic routes -----------------------------------------------------------
@app.get("/", include_in_schema=False)
def root():
    return {"message": "API running. Open the dashboard at http://localhost:3000"}


@app.get("/health")
def health():
    return {"status": "ok"}


# -- dashboard API ----------------------------------------------------------
@app.post("/api/analyze", status_code=202)
def analyze_async(req: AnalyzeRequest):
    src = Path(req.source)
    if not src.is_absolute():
        src = ROOT / src
    if not src.exists():
        raise HTTPException(404, f"Source not found: {req.source}")
    if _job["state"] == "running":
        raise HTTPException(409, "An analysis is already running")

    _job.update(state="running", source=str(src), count=0, error=None)
    threading.Thread(target=_run_job, args=(str(src),), daemon=True).start()
    return {"started": True, "source": str(src)}


@app.get("/api/status")
def status():
    return _job


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
    LOG_PATH.unlink(missing_ok=True)
    return {"cleared": True}


# -- photo number plate recognition ----------------------------------------

_photo_alpr = None


def get_photo_alpr():
    global _photo_alpr
    if _photo_alpr is None:
        _photo_alpr = ALPR(ocr_model="cct-xs-v2-global-model")
    return _photo_alpr


@app.post("/api/recognize-photo")
async def recognize_photo(file: UploadFile = File(...)):
    allowed_types = {"image/jpeg", "image/png"}

    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail="Please upload a JPG or PNG image."
        )

    image_bytes = await file.read()

    if not image_bytes:
        raise HTTPException(status_code=400, detail="The uploaded image is empty.")

    if len(image_bytes) > 15 * 1024 * 1024:
        raise HTTPException(
            status_code=413,
            detail="Image is too large. Maximum size is 15 MB."
        )

    suffix = ".png" if file.content_type == "image/png" else ".jpg"

    try:
        with tempfile.NamedTemporaryFile(suffix=suffix) as temp_file:
            temp_file.write(image_bytes)
            temp_file.flush()

            results = get_photo_alpr().predict(temp_file.name)

        plates = []

        for result in results:
            box = result.detection.bounding_box
            plates.append({
                "text": (result.ocr.text or "").strip() or None,
                "detection_confidence": round(
                    float(result.detection.confidence), 3
                ),
                "box": {
                    "x1": int(box.x1),
                    "y1": int(box.y1),
                    "x2": int(box.x2),
                    "y2": int(box.y2),
                },
            })

        return {
            "filename": file.filename,
            "plate_count": len(plates),
            "plates": plates,
            "message": (
                "Recognition complete."
                if any(p["text"] for p in plates)
                else "No readable plate text found."
            ),
        }

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Photo recognition failed: {exc}"
        ) from exc

# -- original routes,