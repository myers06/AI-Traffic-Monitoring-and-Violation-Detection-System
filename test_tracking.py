
from ultralytics import YOLO
import csv

# Load the YOLO model
model = YOLO("yolo11n.pt")

video_path = "videos/traffic.mp4"
csv_path = "vehicle_tracking.csv"

print("Starting vehicle detection and tracking...")

# Open a CSV file to save tracking data
with open(csv_path, mode="w", newline="", encoding="utf-8") as file:
    writer = csv.writer(file)

    # Write the CSV column headings
    writer.writerow([
        "frame",
        "track_id",
        "class_name",
        "x1",
        "y1",
        "x2",
        "y2",
        "confidence"
    ])

    # Process the video frame by frame
    results = model.track(
        source=video_path,
        show=True,
        save=True,
        tracker="bytetrack.yaml",
        classes=[2, 3, 5, 7],
        stream=True
    )

    for frame_number, result in enumerate(results):
        boxes = result.boxes

        if boxes is None or boxes.id is None:
            continue

        # Get bounding boxes, tracking IDs, classes and confidence scores
        coordinates = boxes.xyxy.cpu().tolist()
        track_ids = boxes.id.int().cpu().tolist()
        class_ids = boxes.cls.int().cpu().tolist()
        confidences = boxes.conf.cpu().tolist()

        for box, track_id, class_id, confidence in zip(
            coordinates, track_ids, class_ids, confidences
        ):
            class_name = model.names[class_id]
            x1, y1, x2, y2 = box

            writer.writerow([
                frame_number,
                track_id,
                class_name,
                round(x1, 2),
                round(y1, 2),
                round(x2, 2),
                round(y2, 2),
                round(confidence, 4)
            ])

print(f"Tracking complete! CSV saved to: {csv_path}")
