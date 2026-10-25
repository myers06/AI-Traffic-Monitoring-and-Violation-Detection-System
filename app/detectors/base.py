from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Detection:
    label: str                        # "person", "motorcycle", ...
    box: tuple                        # (x1, y1, x2, y2)
    conf: float
    track_id: int | None = None


@dataclass
class Violation:
    type: str                         # "triple_riding", "no_helmet", "red_light"
    track_id: int
    frame_idx: int
    box: tuple
    details: dict = field(default_factory=dict)

    def label(self) -> str:
        return self.type.replace("_", " ").upper()

    def to_dict(self) -> dict:
        return {
            "type": self.type,
            "track_id": self.track_id,
            "frame_idx": self.frame_idx,
            "box": [round(float(v), 1) for v in self.box],
            "details": self.details,
        }


class BaseDetector(ABC):
    name = "base"

    @abstractmethod
    def process(self, frame_idx: int, frame, detections: list[Detection]) -> list[Violation]:
        ...

    def reset(self) -> None:
        """Clear per-video state."""