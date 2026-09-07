import cv2
from ultralytics import YOLO
from paddleocr import PaddleOCR


class ANPRPipeline:

    def __init__(self):

        print("Loading license plate detector...")

        self.plate_detector = YOLO(
            "ai/models/license_plate.pt"
        )

        print("Loading PaddleOCR...")

        self.ocr = PaddleOCR(
            lang="en"
        )

        print("ANPR pipeline ready.")

    def read_plate(self, plate_crop):

        # Resize while keeping OCR image below 4000 pixels
        height, width = plate_crop.shape[:2]

        scale = min(5.0, 3800 / max(height, width))

        if scale > 1:
            new_width = int(width * scale)
            new_height = int(height * scale)

            plate_crop = cv2.resize(
                plate_crop,
                (new_width, new_height),
                interpolation=cv2.INTER_CUBIC
            )

        # Improve contrast
        gray = cv2.cvtColor(
            plate_crop,
            cv2.COLOR_BGR2GRAY
        )

        clahe = cv2.createCLAHE(
            clipLimit=2.0,
            tileGridSize=(8, 8)
        )

        enhanced = clahe.apply(gray)

        # PaddleOCR expects 3-channel image
        enhanced = cv2.cvtColor(
            enhanced,
            cv2.COLOR_GRAY2BGR
        )

        results = self.ocr.predict(enhanced)

        best_text = ""
        best_score = 0.0

        for result in results:

            data = result.json

            if callable(data):
                data = data()

            texts = data.get(
                "rec_texts",
                []
            )

            scores = data.get(
                "rec_scores",
                []
            )

            for text, score in zip(
                texts,
                scores
            ):

                text = str(text).strip()
                score = float(score)

                if text and score > best_score:

                    best_text = text
                    best_score = score

        return best_text, best_score

    def detect_and_read(self, image):

        results = self.plate_detector(
            image,
            verbose=False
        )

        detections = []

        for result in results:

            for box in result.boxes:

                detection_confidence = float(
                    box.conf[0]
                )

                if detection_confidence < 0.25:
                    continue

                x1, y1, x2, y2 = map(
                    int,
                    box.xyxy[0].tolist()
                )

                plate_crop = image[
                    y1:y2,
                    x1:x2
                ]

                if plate_crop.size == 0:
                    continue

                plate_text, ocr_confidence = (
                    self.read_plate(plate_crop)
                )

                detections.append({
                    "text": plate_text,
                    "detection_confidence":
                        detection_confidence,
                    "ocr_confidence":
                        ocr_confidence,
                    "bbox":
                        [x1, y1, x2, y2]
                })

        return detections