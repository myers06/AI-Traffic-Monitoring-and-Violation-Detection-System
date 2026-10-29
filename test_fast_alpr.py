import cv2
from fast_alpr import ALPR

image_path = "output/violations/triple_riding_id20_f86_20261027_143427.jpg"

image = cv2.imread(image_path)
if image is None:
    raise SystemExit(f"Could not open image: {image_path}")

alpr = ALPR()
results = alpr.predict(image)

print("\n--- FastALPR test results ---")
print(results)
