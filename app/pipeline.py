
import cv2
from datetime import datetime
from ultralytics import YOLO
from fast_alpr import ALPR

from app.detectors import build_detectors
from app.detectors.base import Detection
from app.utils.drawing import draw_detections, draw_violations
from app.utils.evidence import EvidenceWriter
from app.database import save_violation


class ViolationPipeline:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.model = YOLO(cfg["model"]["weights"])
        self.alpr = ALPR()
        self.detectors = build_detectors(cfg)
        self.evidence = EvidenceWriter(
            cfg["output"]["dir"],
            cfg["output"]["save_frames"]
        )

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
                int(i) if i is not None else None
            )
            for b, c, s, i in zip(xyxy, cls, conf, ids)
        ]

    def process_frame(self, frame_idx: int, frame):
        detections = self._detect(frame)
        violations = []

        for detector in self.detectors:
            violations.extend(
                detector.process(frame_idx, frame, detections)
            )

        return detections, violations

    def _recognize_plate(self, frame, violation_box):
        """Detect plates in the frame and select one overlapping the violation."""
        plate_number = None
        plate_confidence = 0.0

        try:
            results = self.alpr.predict(frame)
            vx1, vy1, vx2, vy2 = map(float, violation_box)

            candidates = []

            for result in results:
                box = result.detection.bounding_box
                px1, py1, px2, py2 = box.x1, box.y1, box.x2, box.y2

                # Keep plates whose centre lies inside the violation box.
                cx = (px1 + px2) / 2
                cy = (py1 + py2) / 2

                if not (vx1 <= cx <= vx2 and vy1 <= cy <= vy2):
                    continue

                text = (result.ocr.text or "").strip().upper()
                text = "".join(ch for ch in text if ch.isalnum())

                if not text:
                    continue

                ocr_scores = result.ocr.confidence or []
                ocr_confidence = (
                    sum(ocr_scores) / len(ocr_scores)
                    if ocr_scores else 0.0
                )

                # Ignore very short OCR results that are unlikely to be
                # complete registration numbers.
                if len(text) < 5:
                    continue

                combined_confidence = (
                    float(result.detection.confidence)
                    * float(ocr_confidence)
                )
                candidates.append((text, combined_confidence))

            if candidates:
                plate_number, plate_confidence = max(
                    candidates, key=lambda item: item[1]
                )

        except Exception as exc:
            print(f"FastALPR recognition failed: {exc}")

        return plate_number, round(float(plate_confidence), 3)

    def run(
        self,
        source,
        show: bool = False,
        save_video: str | None = None
    ) -> list[dict]:

        if isinstance(source, str) and source.isdigit():
            source = int(source)

        cap = cv2.VideoCapture(source)

        if not cap.isOpened():
            raise RuntimeError(f"Cannot open source: {source}")

        self.model.predictor = None

        for detector in self.detectors:
            detector.reset()

        writer = None

        if save_video:
            fps = cap.get(cv2.CAP_PROP_FPS) or 25
            size = (
                int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
                int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            )

            writer = cv2.VideoWriter(
                save_video,
                cv2.VideoWriter_fourcc(*"mp4v"),
                fps,
                size
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

                if idx % skip:
                    continue

                detections, violations = self.process_frame(idx, frame)

                if violations or show or writer:
                    vis = draw_detections(frame.copy(), detections)
                    vis = draw_violations(vis, violations)

                    for violation in violations:
                        record = self.evidence.save(violation, vis)
                        records.append(record)

                        plate_number, plate_confidence = (
                            self._recognize_plate(frame, violation.box)
                        )

                        save_violation(
                            plate_number=plate_number,
                            plate_confidence=plate_confidence,
                            violation_type=record.get("type", "unknown"),
                            track_id=record.get("track_id"),
                            timestamp=record.get(
                                "timestamp", datetime.now().isoformat()
                            ),
                            evidence_image=record.get("image")
                        )

                    if writer:
                        writer.write(vis)

                    if show:
                        cv2.imshow("Traffic Violations", vis)

                        if cv2.waitKey(1) & 0xFF == ord("q"):
                            break

        finally:
            cap.release()

            if writer:
                writer.release()

            if show:
                cv2.destroyAllWindows()

        return records
set