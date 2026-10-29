
'''
import cv2
import easyocr
import numpy as np


# Initialize OCR once and reuse it.
_reader = easyocr.Reader(["en"], gpu=False)


def recognize_plate(plate_image: np.ndarray) -> dict:
    """
    Read text from an image containing a cropped license plate.

    Note: This function reads text; it does not locate
    the license plate inside a full traffic image.
    """
    if plate_image is None or plate_image.size == 0:
        return {"plate_number": None, "confidence": 0.0}

    # Convert the image to grayscale and enlarge it.
    gray = cv2.cvtColor(plate_image, cv2.COLOR_BGR2GRAY)
    enlarged = cv2.resize(
        gray,
        None,
        fx=2,
        fy=2,
        interpolation=cv2.INTER_CUBIC,
    )

    # Read likely registration characters.
    results = _reader.readtext(
        enlarged,
        allowlist="ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789",
        detail=1,
    )

    if not results:
        return {"plate_number": None, "confidence": 0.0}

    # Combine text detected across the plate.
    plate_number = "".join(
        item[1].upper().replace(" ", "")
        for item in results
    )

    confidence = sum(item[2] for item in results) / len(results)

    return {
        "plate_number": plate_number or None,
        "confidence": round(float(confidence), 3),
    }
'''

import sys

import cv2

from plate_ocr import recognize_plate  # your existing file


# Plate detector bundled with OpenCV (no extra download needed).
_cascade = cv2.CascadeClassifier(
    cv2.data.haarcascades + "haarcascade_russian_plate_number.xml"
)


def detect_plates(frame):
    """Return (x, y, w, h) boxes for likely plates in a full frame."""
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    return _cascade.detectMultiScale(
        gray, scaleFactor=1.1, minNeighbors=4, minSize=(60, 20)
    )


def recognize_video(
    source,
    frame_step=5,       # run OCR every Nth frame
    min_conf=0.4,       # drop low-confidence reads
    min_len=4,          # drop junk reads like "A1"
    output_path=None,   # optional annotated video
):
    """
    source: video file path, or 0 for webcam.
    Returns plates sorted by how often they were seen.
    """
    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        raise ValueError(f"Could not open video: {source}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    writer = None
    if output_path:
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        writer = cv2.VideoWriter(
            output_path, cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h)
        )

    seen = {}
    last_boxes = []
    idx = 0

    while True:
        ok, frame = cap.read()
        if not ok:
            break

        if idx % frame_step == 0:
            last_boxes = []
            fh, fw = frame.shape[:2]

            for (x, y, w, h) in detect_plates(frame):
                # Small padding so edge characters aren't clipped.
                px, py = int(w * 0.05), int(h * 0.1)
                x1, y1 = max(x - px, 0), max(y - py, 0)
                x2, y2 = min(x + w + px, fw), min(y + h + py, fh)

                result = recognize_plate(frame[y1:y2, x1:x2])
                text, conf = result["plate_number"], result["confidence"]

                if not text or len(text) < min_len or conf < min_conf:
                    last_boxes.append((x, y, w, h, None))
                    continue

                t = round(idx / fps, 2)
                entry = seen.get(text)
                if entry is None:
                    seen[text] = {
                        "plate_number": text,
                        "best_confidence": conf,
                        "hits": 1,
                        "first_seen_sec": t,
                        "last_seen_sec": t,
                    }
                else:
                    entry["hits"] += 1
                    entry["best_confidence"] = max(entry["best_confidence"], conf)
                    entry["last_seen_sec"] = t

                last_boxes.append((x, y, w, h, text))

        if writer:
            for (x, y, w, h, text) in last_boxes:
                cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
                if text:
                    cv2.putText(frame, text, (x, y - 8),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
            writer.write(frame)

        idx += 1

    cap.release()
    if writer:
        writer.release()

    return sorted(seen.values(), key=lambda p: p["hits"], reverse=True)


if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else 0
    src = int(src) if str(src).isdigit() else src
    out = sys.argv[2] if len(sys.argv) > 2 else None

    for plate in recognize_video(src, output_path=out):
        print(plate)