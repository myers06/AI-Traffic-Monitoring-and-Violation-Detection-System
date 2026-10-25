from app.detectors.base import BaseDetector


class NoHelmetDetector(BaseDetector):
    name = "no_helmet"

    def __init__(self, cfg: dict):
        self.cfg = cfg

    def process(self, frame_idx, frame, detections):
        return []  # TODO