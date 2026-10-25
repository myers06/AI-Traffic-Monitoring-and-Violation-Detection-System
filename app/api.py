import json
import threading
from collections import Counter
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.config import ROOT, load_config
from app.pipeline import ViolationPipeline

app = FastAPI(title="Traffic Violation Detection")

_cfg = load_config()
OUT_DIR = Path(_cfg["output"]["dir"])
OUT_DIR.mkdir(parents=True, exist_ok=True)
LOG_PATH = OUT_DIR / "violations.jsonl"

app.mount("/evidence", StaticFiles(directory=str(OUT_DIR)), name="evidence")

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


# -- original routes,