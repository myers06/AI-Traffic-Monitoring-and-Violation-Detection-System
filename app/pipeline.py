from collections import defaultdict
from datetime import datetime
from pathlib import Path
import re

import cv2
from fast_alpr import ALPR
from ultralytics import YOLO

from app.database import save_plate, save_violation, update_violation_plate
from app.detectors import build_detectors
from app.detectors.base import Detection
from app.utils.drawing import draw_detections, draw_violations
from app.utils.evidence import EvidenceWriter

VEHICLES = {"car", "motorcycle", "bus", "truck"}


class ViolationPipeline:
    """One pass over a video: detects violations AND reads every vehicle's plate."""

    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.model = YOLO(cfg["model"]["weights"])
        self.alpr = ALPR(ocr_model="cct-xs-v2-global-model")
        self.detectors = build_detectors(cfg)
        self.evidence = EvidenceWriter(
            cfg["output"]["dir"], cfg["output"]["save_frames"]
        )

        p = cfg.get("plates", {})
        self.plates_enabled = p.get("enabled", True)
        self.plate_pad = p.get("crop_padding", 0.15)
        self.plate_min_len = p.get("min_length", 5)
        self.plate_good_conf = p.get("good_confidence", 0.6)
        self.plate_every = p.get("scan_every_frames", 5)
        self.plate_max_attempts = p.get("max_attempts", 15)
        self.plate_min_vehicle_px = p.get("min_vehicle_width", 80)
        self.plate_stale_after = p.get("stale_after_frames", 60)

        self.plates_dir = Path(cfg["output"]["dir"]) / "plates"
        self.plates_dir.mkdir(parents=True, exist_ok=True)

        self._tracks: dict[int, dict] = {}
        self._violation_rows: dict[int, list[int]] = defaultdict(list)
        self._video = ""
        self._fps = 25.0

    # -- detection ------------------------------------------------------------
    def _detect(self, frame) -> list[Detection]:
        m = self.cfg["model"]
        res = self.model.track(
            frame,
            persist=True,
            conf=m["conf"],
            iou=m["iou"],
            imgsz=m["imgsz"],
            device=m["device"],
            tracker=m["tracker"],
            classes=list(self.cfg["classes"].values()),
            verbose=False,
        )[0]

        boxes = res.boxes
        if boxes is None or len(boxes) == 0:
            return []

        xyxy = boxes.xyxy.cpu().numpy()
        cls = boxes.cls.cpu().numpy().astype(int)
        conf = boxes.conf.cpu().numpy()
        ids = (
            boxes.id.cpu().numpy().astype(int)
            if boxes.id is not None
            else [None] * len(xyxy)
        )

        return [
            Detection(
                res.names[c],
                tuple(map(float, b)),
                float(s),
                int(i) if i is not None else None,
            )
            for b, c, s, i in zip(xyxy, cls, conf, ids)
        ]

    def process_frame(self, frame_idx: int, frame):
        detections = self._detect(frame)
        violations = []
        for detector in self.detectors:
            violations.extend(detector.process(frame_idx, frame, detections))
        return detections, violations

    # -- plate reading --------------------------------------------------------
    def _crop(self, frame, box):
        """Padded crop around a box. The plate detector runs at 384px, so
        cropping the vehicle keeps plates readable in 4K frames."""
        h, w = frame.shape[:2]
        x1, y1, x2, y2 = map(float, box)
        px, py = (x2 - x1) * self.plate_pad, (y2 - y1) * self.plate_pad
        x1, y1 = max(int(x1 - px), 0), max(int(y1 - py), 0)
        x2, y2 = min(int(x2 + px), w), min(int(y2 + py), h)
        if x2 - x1 < 10 or y2 - y1 < 10:
            return None
        return frame[y1:y2, x1:x2]

    def _read_plate(self, image):
        """Best plate in image -> (text, confidence, plate_crop) or (None, 0, None)."""
        if image is None or image.size == 0:
            return None, 0.0, None
        try:
            results = self.alpr.predict(image)
        except Exception as exc:
            print(f"FastALPR recognition failed: {exc}")
            return None, 0.0, None

        best = (None, 0.0, None)
        for r in results:
            ocr = r.ocr
            if ocr is None or not ocr.text:
                continue
            text = "".join(ch for ch in ocr.text.upper() if ch.isalnum())
            if len(text) < self.plate_min_len:
                continue

            c = ocr.confidence  # float or one value per character
            if isinstance(c, (list, tuple)):
                ocr_conf = sum(c) / len(c) if c else 0.0
            else:
                ocr_conf = float(c or 0.0)
            conf = float(r.detection.confidence) * ocr_conf

            if conf > best[1]:
                b = r.detection.bounding_box
                h, w = image.shape[:2]
                x1, y1 = max(int(b.x1) - 4, 0), max(int(b.y1) - 4, 0)
                x2, y2 = min(int(b.x2) + 4, w), min(int(b.y2) + 4, h)
                plate_img = image[y1:y2, x1:x2].copy() if x2 > x1 and y2 > y1 else None
                best = (text, round(conf, 3), plate_img)
        return best

    def _scan_plates(self, frame_idx, frame, detections):
        for d in detections:
            if d.label not in VEHICLES or d.track_id is None:
                continue

            st = self._tracks.get(d.track_id)
            if st is None:
                st = self._tracks[d.track_id] = {
                    "vehicle": d.label,
                    "first": frame_idx,
                    "last": frame_idx,
                    "last_try": -10**9,
                    "attempts": 0,
                    "votes": defaultdict(float),
                    "best_conf": {},
                    "best_img": {},
                    "done": False,
                }
            st["last"] = frame_idx

            if st["done"] or frame_idx - st["last_try"] < self.plate_every:
                continue
            if d.box[2] - d.box[0] < self.plate_min_vehicle_px:
                continue  # too far away to read yet

            st["last_try"] = frame_idx
            st["attempts"] += 1

            text, conf, plate_img = self._read_plate(self._crop(frame, d.box))
            if text:
                st["votes"][text] += conf
                if conf > st["best_conf"].get(text, 0.0):
                    st["best_conf"][text] = conf
                    st["best_img"][text] = plate_img

                # a violation on this vehicle gets the best read so far
                for row_id in self._violation_rows.get(d.track_id, []):
                    t, c = self._current_best(st)
                    update_violation_plate(row_id, t, c)

            if (
                max(st["best_conf"].values(), default=0) >= self.plate_good_conf
                and st["attempts"] >= 3
            ) or st["attempts"] >= self.plate_max_attempts:
                st["done"] = True

        stale = [
            tid for tid, st in self._tracks.items()
            if frame_idx - st["last"] > self.plate_stale_after
        ]
        for tid in stale:
            self._finalize(tid)

    @staticmethod
    def _current_best(st):
        if not st["votes"]:
            return None, 0.0
        text = max(st["votes"], key=st["votes"].get)  # most agreed-on read
        return text, st["best_conf"][text]

    def _finalize(self, tid):
        st = self._tracks.pop(tid, None)
        if not st or not st["votes"]:
            return

        text, conf = self._current_best(st)
        image_name = None
        img = st["best_img"].get(text)
        if img is not None and img.size:
            if img.shape[0] < 60:  # enlarge small crops so they're viewable
                scale = 60 / img.shape[0]
                img = cv2.resize(img, None, fx=scale, fy=scale,
                                 interpolation=cv2.INTER_CUBIC)
            stem = re.sub(r"[^A-Za-z0-9_-]", "_", Path(self._video).stem)[:40]
            image_name = f"plates/{stem}_id{tid}_{text}.jpg"
            cv2.imwrite(str(self.plates_dir.parent / image_name), img)

        save_plate(
            video=self._video,
            track_id=tid,
            vehicle=st["vehicle"],
            plate_number=text,
            plate_confidence=conf,
            first_seen_sec=round(st["first"] / self._fps, 2),
            last_seen_sec=round(st["last"] / self._fps, 2),
            image=image_name,
        )
        for row_id in self._violation_rows.get(tid, []):
            update_violation_plate(row_id, text, conf)
        print(f"Plate: {text} ({conf:.2f}) {st['vehicle']} #{tid}")

    # -- main loop ------------------------------------------------------------
    def run(
        self,
        source,
        show: bool = False,
        save_video: str | None = None,
        video_label: str | None = None,
        progress=None,
    ) -> list[dict]:
        if isinstance(source, str) and source.isdigit():
            source = int(source)

        cap = cv2.VideoCapture(source)
        if not cap.isOpened():
            raise RuntimeError(f"Cannot open source: {source}")

        self.model.predictor = None  # fresh tracker per video
        for detector in self.detectors:
            detector.reset()
        self._tracks = {}
        self._violation_rows = defaultdict(list)
        self._video = video_label or str(source)
        self._fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)

        writer = None
        if save_video:
            size = (
                int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
                int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
            )
            writer = cv2.VideoWriter(
                save_video, cv2.VideoWriter_fourcc(*"mp4v"), self._fps, size
            )

        skip = max(1, self.cfg["video"]["frame_skip"])
        records: list[dict] = []
        idx = -1

        try:
            while True:
                ok, frame = cap.read()
                if not ok:
                    break
                idx += 1

                if progress and total and idx % 30 == 0:
                    progress(min(idx / total, 0.99))

                if idx % skip:
                    continue

                detections, violations = self.process_frame(idx, frame)

                if self.plates_enabled:
                    self._scan_plates(idx, frame, detections)

                if violations or show or writer:
                    vis = draw_detections(frame.copy(), detections)
                    vis = draw_violations(vis, violations)

                    for violation in violations:
                        record = self.evidence.save(violation, vis)
                        records.append(record)

                        text, conf = None, 0.0
                        st = self._tracks.get(violation.track_id)
                        if st:
                            text, conf = self._current_best(st)

                        row_id = save_violation(
                            plate_number=text,
                            plate_confidence=conf,
                            violation_type=record.get("type", "unknown"),
                            track_id=record.get("track_id"),
                            timestamp=record.get(
                                "timestamp", datetime.now().isoformat()
                            ),
                            evidence_image=record.get("image"),
                        )
                        if violation.track_id is not None:
                            self._violation_rows[violation.track_id].append(row_id)

                    if writer:
                        writer.write(vis)
                    if show:
                        cv2.imshow("Traffic Violations", vis)
                        if cv2.waitKey(1) & 0xFF == ord("q"):
                            break
        finally:
            for tid in list(self._tracks):
                self._finalize(tid)
            cap.release()
            if writer:
                writer.release()
            if show:
                cv2.destroyAllWindows()
            if progress:
                progress(1.0)

        return records
