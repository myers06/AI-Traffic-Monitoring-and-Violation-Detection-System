from app.detectors.base import BaseDetector
from app.detectors.triple_riding import TripleRidingDetector


def build_detectors(cfg: dict) -> list[BaseDetector]:
    detectors: list[BaseDetector] = []
    if cfg.get("triple_riding", {}).get("enabled", False):
        detectors.append(TripleRidingDetector(cfg))
    # no_helmet / red_light get registered here once implemented
    return detectors