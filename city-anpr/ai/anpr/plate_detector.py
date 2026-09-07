from ultralytics import YOLO


class LicensePlateDetector:
    """
    Detects license plates using a custom YOLO model.
    """

    def __init__(self, model_path="ai/models/license_plate.pt"):
        self.model = YOLO(model_path)

    def detect(self, image):
        results = self.model(
            image,
            verbose=False
        )

        plates = []

        for result in results:
            for box in result.boxes:

                confidence = float(box.conf[0])

                x1, y1, x2, y2 = map(
                    int,
                    box.xyxy[0].tolist()
                )

                plates.append({
                    "confidence": confidence,
                    "bbox": [x1, y1, x2, y2]
                })

        return plates