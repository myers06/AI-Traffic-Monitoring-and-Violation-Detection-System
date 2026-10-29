from pathlib import Path
from fast_alpr import ALPR

image_dir = Path("test_images")
models = [
    "cct-xs-v2-global-model",
    "cct-s-v2-global-model",
]

for model_name in models:
    print(f"\n{'=' * 55}")
    print(f"OCR MODEL: {model_name}")
    print("=" * 55)

    alpr = ALPR(ocr_model=model_name)

    for image_path in sorted(image_dir.iterdir()):
        if image_path.suffix.lower() not in {".jpg", ".jpeg", ".png"}:
            continue

        results = alpr.predict(str(image_path))
        print(f"\n{image_path.name}")

        if not results:
            print("  No plates detected")
            continue

        for result in results:
            text = (result.ocr.text or "").strip()
            print(
                f"  Text: {text or 'Not recognized'} | "
                f"Detection confidence: {result.detection.confidence:.2f}"
            )

print("\nComparison complete.")
