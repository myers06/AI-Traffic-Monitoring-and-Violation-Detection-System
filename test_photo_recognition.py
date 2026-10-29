
from pathlib import Path
import cv2
from fast_alpr import ALPR

input_dir = Path("test_images")
output_dir = Path("output/plate_tests")
output_dir.mkdir(parents=True, exist_ok=True)

alpr = ALPR()

for image_path in sorted(input_dir.iterdir()):
    if image_path.suffix.lower() not in {".jpg", ".jpeg", ".png"}:
        continue

    image = cv2.imread(str(image_path))
    if image is None:
        print(f"Could not open: {image_path.name}")
        continue

    print(f"\n--- {image_path.name} ---")
    results = alpr.predict(str(image_path))

    if not results:
        print("No plate detected.")
        continue

    for index, result in enumerate(results, start=1):
        box = result.detection.bounding_box
        text = (result.ocr.text or "").strip()
        confidence = float(result.detection.confidence)

        print(f"Plate {index}: {text or 'Text not recognized'}")
        print(f"Detection confidence: {confidence:.2f}")

        x1 = max(0, int(box.x1))
        y1 = max(0, int(box.y1))
        x2 = min(image.shape[1], int(box.x2))
        y2 = min(image.shape[0], int(box.y2))

        if x2 > x1 and y2 > y1:
            crop = image[y1:y2, x1:x2]
            crop_path = output_dir / f"{image_path.stem}_plate_{index}.jpg"
            cv2.imwrite(str(crop_path), crop)
            print(f"Saved crop: {crop_path}")

print("\nFinished testing all photos.")

