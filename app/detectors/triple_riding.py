from collections import defaultdict

from app.detectors.base import BaseDetector, Detection, Violation
from app.utils.geometry import overlap_ratio, rider_zone, union_box


class TripleRidingDetector(BaseDetector):
    name = "triple_riding"

    def __init__(self, cfg: dict):
        c = cfg["triple_riding"]
        self.min_riders = c["min_riders"]
        self.min_overlap = c["min_overlap"]
        self.expand_top = c["zone_expand_top"]
        self.expand_side = c["zone_expand_side"]
        self.min_frames = c["min_consecutive_frames"]
        self.stale_after = c["stale_after_frames"]
        self.reset()

    def reset(self) -> None:
        self._streak: dict[int, int] = defaultdict(int)
        self._last_seen: dict[int, int] = {}
        self._flagged: set[int] = set()

    # -- rider assignment ---------------------------------------------------
    def assign_riders(self, motos: list[Detection],
                      persons: list[Detection]) -> dict[int, list[Detection]]:
        """Assign each person to at most one motorcycle (the best-overlapping one)."""
        zones = {
            m.track_id: rider_zone(m.box, self.expand_top, self.expand_side)
            for m in motos
        }
        assigned: dict[int, list[Detection]] = defaultdict(list)
        for p in persons:
            best_id, best_score = None, self.min_overlap
            for mid, zone in zones.items():
                score = overlap_ratio(p.box, zone)
                if score >= best_score:
                    best_id, best_score = mid, score
            if best_id is not None:
                assigned[best_id].append(p)
        return assigned

    # -- main entry ---------------------------------------------------------
    def process(self, frame_idx, frame, detections):
        motos = [d for d in detections if d.label == "motorcycle" and d.track_id is not None]
        persons = [d for d in detections if d.label == "person"]
        assigned = self.assign_riders(motos, persons)

        violations: list[Violation] = []
        for m in motos:
            tid = m.track_id
            riders = assigned.get(tid, [])
            self._last_seen[tid] = frame_idx

            if len(riders) >= self.min_riders:
                self._streak[tid] += 1
            else:
                self._streak[tid] = 0

            if self._streak[tid] >= self.min_frames and tid not in self._flagged:
                self._flagged.add(tid)
                violations.append(Violation(
                    type=self.name,
                    track_id=tid,
                    frame_idx=frame_idx,
                    box=union_box([m.box] + [r.box for r in riders]),
                    details={"rider_count": len(riders)},
                ))

        self._expire(frame_idx)
        return violations

    def _expire(self, frame_idx: int) -> None:
        stale = [t for t, last in self._last_seen.items()
                 if frame_idx - last > self.stale_after]
        for t in stale:
            self._last_seen.pop(t, None)
            self._streak.pop(t, None)
            # keep _flagged so a re-appearing ID isn't double counted