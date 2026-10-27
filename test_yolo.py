
from ultralytics import YOLO

# Load a pretrained YOLO model
model = YOLO("yolo11n.pt")

# Run object detection on a sample image
results = model.predict(
    source="https://ultralytics.com/images/bus.jpg",
    show=True,
    save=True
)

print("Detection completed successfully!")
