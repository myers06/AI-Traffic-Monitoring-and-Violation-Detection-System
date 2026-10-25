import cv2

GREEN = (0, 200, 0)
RED = (0, 0, 255)


def _label(frame, text, x, y, color):
    (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
    y = max(y, th + 6)
    cv2.rectangle(frame, (x, y - th - 6), (x + tw + 4, y), color, -1)
    cv2.putText(frame, text, (x + 2, y - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                (255, 255, 255), 1, cv2.LINE_AA)


def draw_detections(frame, detections):
    for d in detections:
        x1, y1, x2, y2 = map(int, d.box)
        cv2.rectangle(frame, (x1, y1), (x2, y2), GREEN, 1)
        tag = f"{d.label}" + (f" #{d.track_id}" if d.track_id is not None else "")
        _label(frame, tag, x1, y1, GREEN)
    return frame


def draw_violations(frame, violations):
    for v in violations:
        x1, y1, x2, y2 = map(int, v.box)
        cv2.rectangle(frame, (x1, y1), (x2, y2), RED, 3)
        _label(frame, v.label(), x1, y1, RED)
    return frame