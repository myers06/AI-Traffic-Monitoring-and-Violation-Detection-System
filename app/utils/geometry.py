Box = tuple[float, float, float, float]  # x1, y1, x2, y2


def area(b: Box) -> float:
    return max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])


def intersection_area(a: Box, b: Box) -> float:
    x1, y1 = max(a[0], b[0]), max(a[1], b[1])
    x2, y2 = min(a[2], b[2]), min(a[3], b[3])
    return max(0.0, x2 - x1) * max(0.0, y2 - y1)


def overlap_ratio(inner: Box, outer: Box) -> float:
    """Fraction of `inner`'s area that lies inside `outer`."""
    a = area(inner)
    return intersection_area(inner, outer) / a if a > 0 else 0.0


def union_box(boxes: list[Box]) -> Box:
    return (
        min(b[0] for b in boxes),
        min(b[1] for b in boxes),
        max(b[2] for b in boxes),
        max(b[3] for b in boxes),
    )


def rider_zone(moto: Box, expand_top: float, expand_side: float) -> Box:
    """Region where riders sit: the bike box stretched upward and slightly sideways."""
    w, h = moto[2] - moto[0], moto[3] - moto[1]
    return (
        moto[0] - w * expand_side,
        moto[1] - h * expand_top,
        moto[2] + w * expand_side,
        moto[3],
    )