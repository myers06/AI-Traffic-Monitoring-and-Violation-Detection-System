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
