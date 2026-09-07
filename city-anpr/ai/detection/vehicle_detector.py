from ultralytics import YOLO


class VehicleDetector:
    """
    Detects vehicles using YOLO.
    """

    VEHICLE_CLASSES = {
        2: "car",
        3: "motorcycle",
        5: "bus",
        7: "truck",
    }

    def __init__(self, model_path="yolo11n.pt"):
        self.model = YOLO(model_path)

    def detect(self, image):
        """
        Detect vehicles in an image.

        Returns a list of detected vehicles.
        """

        results = self.model(image, verbose=False)

        vehicles = []

        for result in results:
            for box in result.boxes:

                class_id = int(box.cls[0])
                confidence = float(box.conf[0])

                if class_id not in self.VEHICLE_CLASSES:
                    continue

                x1, y1, x2, y2 = map(
                    int,
                    box.xyxy[0].tolist()
                )

                vehicles.append({
                    "class": self.VEHICLE_CLASSES[class_id],
                    "confidence": confidence,
                    "bbox": [x1, y1, x2, y2],
                })

        return vehicles