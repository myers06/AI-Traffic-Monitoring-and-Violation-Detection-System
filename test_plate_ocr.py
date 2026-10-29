
import cv2
import numpy as np
from app.plate_recognition import recognize_plate

# Create a simple sample plate image
image = np.full((120, 420, 3), 255, dtype=np.uint8)
cv2.rectangle(image, (5, 5), (415, 115), (0, 0, 0), 3)
cv2.putText(
    image,
    "RJ14AB1234",
    (20, 78),
    cv2.FONT_HERSHEY_SIMPLEX,
    1.4,
    (0, 0, 0),
    3
)

result = recognize_plate(image)
print("OCR result:", result)
