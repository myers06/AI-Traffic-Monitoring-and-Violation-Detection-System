import json
import threading
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from app.config import load_config
from app.pipeline import ViolationPipeline

app = FastAPI(title="Traffic Violation Detection")

_cfg = load_config()
_pipeline: ViolationPipeline | None = None
_lock = threading.Lock()  # tracker state is shared, so one run at a time


def get_pipeline() -> ViolationPipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = ViolationPipeline(_cfg)
    return _pipeline


class AnalyzeRequest(BaseModel):
    source: str  # path to a video file on the server


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/analyze")
def analyze(req: AnalyzeRequest):
    if not Path(req.source).exists():
        raise HTTPException(404, f"Source not found: {req.source}")
    with _lock:
        records = get_pipeline().run(req.source)
    return {"count": len(records), "violations": records}


@app.get("/violations")
def list_violations(type: str | None = None):
    log = Path(_cfg["output"]["dir"]) / "violations.jsonl"
    if not log.exists():
        return []
    rows = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines() if line]
    return [r for r in rows if type is None or r["type"] == type]