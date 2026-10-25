import pytest

from app.detectors.base import Detection
from app.detectors.triple_riding import TripleRidingDetector

CFG = {
    "triple_riding": {
        "min_riders": 3,
        "min_overlap": 0.4,
        "zone_expand_top": 0.9,
        "zone_expand_side": 0.1,
        "min_consecutive_frames": 3,
        "stale_after_frames": 10,
    }
}

MOTO = Detection("motorcycle", (100, 200, 200, 300), 0.9, track_id=1)


def person(x1, y1, x2, y2):
    return Detection("person", (x1, y1, x2, y2), 0.9)


THREE = [person(100, 100, 140, 260), person(120, 110, 160, 270), person(160, 100, 200, 260)]


@pytest.fixture
def det():
    return TripleRidingDetector(CFG)


def test_flags_after_consecutive_frames_only_once(det):
    results = [det.process(i, None, [MOTO, *THREE]) for i in range(5)]
    assert results[0] == [] and results[1] == []
    assert len(results[2]) == 1
    assert results[2][0].details["rider_count"] == 3
    assert results[3] == [] and results[4] == []  # no duplicate


def test_two_riders_not_flagged(det):
    for i in range(6):
        assert det.process(i, None, [MOTO, *THREE[:2]]) == []


def test_streak_resets_when_count_drops(det):
    det.process(0, None, [MOTO, *THREE])
    det.process(1, None, [MOTO, *THREE])
    det.process(2, None, [MOTO, *THREE[:2]])  # drops to 2 → reset
    assert det.process(3, None, [MOTO, *THREE]) == []


def test_pedestrian_far_away_not_counted(det):
    far = person(600, 100, 640, 260)
    for i in range(6):
        assert det.process(i, None, [MOTO, *THREE[:2], far]) == []


def test_person_assigned_to_single_bike(det):
    moto2 = Detection("motorcycle", (190, 200, 290, 300), 0.9, track_id=2)
    out = det.assign_riders([MOTO, moto2], THREE)
    assert sum(len(v) for v in out.values()) == 3