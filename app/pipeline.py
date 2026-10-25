import cv2
from ultralytics import YOLO

from app.detectors import build_detectors
from app.detectors.base import Detection
from app.utils.drawing import draw_detections, draw_violations
from app.utils.evidence import EvidenceWriter


class ViolationPipeline:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.model = YOLO(cfg["model"]["weights"])
        self.detectors = build_detectors(cfg)
        self.evidence = EvidenceWriter(cfg["output"]["dir"], cfg["output"]["save_frames"])

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
        ids = (boxes.id.cpu().numpy().astype(int)
               if boxes.id is not None else [None] * len(xyxy))

        return [
            Detection(res.names[c], tuple(map(float, b)), float(s),
                      int(i) if i is not None else None)
            for b, c, s, i in zip(xyxy, cls, conf, ids)
        ]

    def process_frame(self, frame_idx: int, frame):
        detections = self._detect(frame)
        violations = []
        for det in self.detectors:
            violations.extend(det.process(frame_idx, frame, detections))
        return detections, violations

    def run(self, source, show: bool = False, save_video: str | None = None) -> list[dict]:
        if isinstance(source, str) and source.isdigit():
            source = int(source)  # webcam index

        cap = cv2.VideoCapture(source)
        if not cap.isOpened():
            raise RuntimeError(f"Cannot open source: {source}")

        # fresh tracker + detector state for every run
        self.model.predictor = None
        for d in self.detectors:
            d.reset()

        writer = None
        if save_video:
            fps = cap.get(cv2.CAP_PROP_FPS) or 25
            size = (int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
                    int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)))
            writer = cv2.VideoWriter(save_video, cv2.VideoWriter_fourcc(*"mp4v"), fps, size)

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
                    for v in violations:
                        records.append(self.evidence.save(v, vis))
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