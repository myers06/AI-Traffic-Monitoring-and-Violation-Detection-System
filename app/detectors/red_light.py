from app.detectors.base import BaseDetector


class RedLightDetector(BaseDetector):
    name = "red_light"

    def __init__(self, cfg: dict):
        self.cfg = cfg

    def process(self, frame_idx, frame, detections):
        return []  # TODO