import json
from datetime import datetime
from pathlib import Path

import cv2


class EvidenceWriter:
    def __init__(self, out_dir: str, save_frames: bool = True):
        self.dir = Path(out_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.log_path = self.dir / "violations.jsonl"
        self.save_frames = save_frames

    def save(self, violation, frame) -> dict:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        record = violation.to_dict()
        record["timestamp"] = datetime.now().isoformat(timespec="seconds")

        if self.save_frames and frame is not None:
            name = f"{violation.type}_id{violation.track_id}_f{violation.frame_idx}_{ts}.jpg"
            cv2.imwrite(str(self.dir / name), frame)
            record["image"] = name

        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
        return record