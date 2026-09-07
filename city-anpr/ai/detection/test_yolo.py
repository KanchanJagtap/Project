from ultralytics import YOLO

# Load YOLO model
model = YOLO("yolo11n.pt")

# Vehicle classes in the COCO dataset
VEHICLE_CLASSES = {
    2: "car",
    3: "motorcycle",
    5: "bus",
    7: "truck"
}

# Run detection
results = model(
    "bus.jpg",
    save=True
)

print("\n===== VEHICLE DETECTION =====")

for result in results:
    for box in result.boxes:

        class_id = int(box.cls[0])
        confidence = float(box.conf[0])

        if class_id in VEHICLE_CLASSES:
            vehicle_type = VEHICLE_CLASSES[class_id]

            print(
                f"Vehicle: {vehicle_type} | "
                f"Confidence: {confidence:.2f}"
            )

print("=============================\n")