from app.utils.geometry import area, intersection_area, overlap_ratio, rider_zone, union_box


def test_area_and_intersection():
    assert area((0, 0, 10, 5)) == 50
    assert intersection_area((0, 0, 10, 10), (5, 5, 15, 15)) == 25
    assert intersection_area((0, 0, 1, 1), (2, 2, 3, 3)) == 0


def test_overlap_ratio():
    assert overlap_ratio((0, 0, 10, 10), (0, 0, 10, 5)) == 0.5


def test_union_box():
    assert union_box([(0, 0, 5, 5), (3, 3, 10, 8)]) == (0, 0, 10, 8)


def test_rider_zone_extends_upward():
    z = rider_zone((100, 200, 200, 300), expand_top=0.9, expand_side=0.1)
    assert z == (90, 110, 210, 300)