import cv2
import numpy as np
import re

from ultralytics import YOLO
from paddleocr import TextRecognition


class ANPRPipeline:

    # ========================================================
    # INITIALIZATION
    # ========================================================

    def __init__(
        self,
        plate_model_path="ai/models/license_plate.pt"
    ):

        print(
            "Loading license plate detector..."
        )

        self.plate_detector = YOLO(
            plate_model_path
        )


        print(
            "Loading PaddleOCR recognition model..."
        )

        self.ocr = TextRecognition(
            model_name="PP-OCRv6_medium_rec"
        )


        print(
            "ANPR pipeline ready."
        )


    # ========================================================
    # ORDER FOUR POINTS
    # ========================================================

    def order_points(self, points):

        ordered = np.zeros(
            (4, 2),
            dtype=np.float32
        )


        sums = points.sum(
            axis=1
        )


        ordered[0] = points[
            np.argmin(sums)
        ]

        ordered[2] = points[
            np.argmax(sums)
        ]


        differences = np.diff(
            points,
            axis=1
        ).reshape(-1)


        ordered[1] = points[
            np.argmin(differences)
        ]

        ordered[3] = points[
            np.argmax(differences)
        ]


        return ordered


    # ========================================================
    # FIND PLATE CORNERS
    # ========================================================

    def find_plate_corners(self, crop):

        gray = cv2.cvtColor(
            crop,
            cv2.COLOR_BGR2GRAY
        )


        candidates = []


        thresholds = [
            170,
            180,
            190,
            200,
            210,
            220,
            230
        ]


        for threshold in thresholds:

            binary = cv2.threshold(
                gray,
                threshold,
                255,
                cv2.THRESH_BINARY
            )[1]


            kernel = cv2.getStructuringElement(
                cv2.MORPH_RECT,
                (15, 15)
            )


            binary = cv2.morphologyEx(
                binary,
                cv2.MORPH_CLOSE,
                kernel
            )


            binary = cv2.morphologyEx(
                binary,
                cv2.MORPH_OPEN,
                np.ones(
                    (3, 3),
                    np.uint8
                )
            )


            contours, _ = cv2.findContours(
                binary,
                cv2.RETR_EXTERNAL,
                cv2.CHAIN_APPROX_SIMPLE
            )


            for contour in contours:

                area = cv2.contourArea(
                    contour
                )


                if area < 5000:
                    continue


                perimeter = cv2.arcLength(
                    contour,
                    True
                )


                approximation = cv2.approxPolyDP(
                    contour,
                    0.02 * perimeter,
                    True
                )


                if len(approximation) != 4:
                    continue


                points = (
                    approximation
                    .reshape(4, 2)
                    .astype(np.float32)
                )


                tl, tr, br, bl = (
                    self.order_points(points)
                )


                top_width = np.linalg.norm(
                    tr - tl
                )

                bottom_width = np.linalg.norm(
                    br - bl
                )

                left_height = np.linalg.norm(
                    bl - tl
                )

                right_height = np.linalg.norm(
                    br - tr
                )


                width = max(
                    top_width,
                    bottom_width
                )

                height = max(
                    left_height,
                    right_height
                )


                if height <= 0:
                    continue


                aspect_ratio = (
                    width / height
                )


                if aspect_ratio < 1.3:
                    continue


                if aspect_ratio > 7.0:
                    continue


                crop_area = (
                    crop.shape[0]
                    * crop.shape[1]
                )


                area_ratio = (
                    area / crop_area
                )


                if area_ratio < 0.20:
                    continue


                score = (
                    area
                    * min(
                        aspect_ratio,
                        5.0
                    )
                )


                candidates.append(
                    (
                        score,
                        points,
                        threshold,
                        area,
                        aspect_ratio
                    )
                )


        if not candidates:

            return None


        candidates.sort(
            key=lambda x: x[0],
            reverse=True
        )


        best = candidates[0]


        return {
            "points": best[1],
            "threshold": best[2],
            "area": best[3],
            "aspect_ratio": best[4]
        }


    # ========================================================
    # PERSPECTIVE CORRECTION
    # ========================================================

    def rectify_plate(self, plate_crop):

        h, w = plate_crop.shape[:2]


        plate_info = (
            self.find_plate_corners(
                plate_crop
            )
        )


        if plate_info is not None:

            corners = self.order_points(
                plate_info["points"]
            )

        else:

            corners = np.float32([
                [0, 0],
                [w - 1, 0],
                [w - 1, h - 1],
                [0, h - 1]
            ])


        tl, tr, br, bl = corners


        width_top = np.linalg.norm(
            tr - tl
        )

        width_bottom = np.linalg.norm(
            br - bl
        )

        height_left = np.linalg.norm(
            bl - tl
        )

        height_right = np.linalg.norm(
            br - tr
        )


        output_width = int(
            max(
                width_top,
                width_bottom
            )
        )


        output_height = int(
            max(
                height_left,
                height_right
            )
        )


        output_width = max(
            output_width,
            1600
        )


        output_height = max(
            output_height,
            600
        )


        destination = np.float32([
            [0, 0],
            [output_width - 1, 0],
            [
                output_width - 1,
                output_height - 1
            ],
            [0, output_height - 1]
        ])


        matrix = cv2.getPerspectiveTransform(
            corners,
            destination
        )


        rectified = cv2.warpPerspective(
            plate_crop,
            matrix,
            (
                output_width,
                output_height
            )
        )


        return rectified


    # ========================================================
    # OCR IMAGE VARIANTS
    # ========================================================

    def create_ocr_variants(self, image):

        variants = {}


        # ----------------------------------------------------
        # Original
        # ----------------------------------------------------

        variants["original"] = image


        # ----------------------------------------------------
        # Enlarged
        # ----------------------------------------------------

        enlarged = cv2.resize(
            image,
            None,
            fx=1.5,
            fy=1.5,
            interpolation=cv2.INTER_CUBIC
        )


        variants["enlarged"] = enlarged


        # ----------------------------------------------------
        # Sharpened
        # ----------------------------------------------------

        blur = cv2.GaussianBlur(
            enlarged,
            (0, 0),
            2
        )


        sharpened = cv2.addWeighted(
            enlarged,
            1.5,
            blur,
            -0.5,
            0
        )


        variants["sharpened"] = sharpened


        # ----------------------------------------------------
        # CLAHE
        # ----------------------------------------------------

        gray = cv2.cvtColor(
            enlarged,
            cv2.COLOR_BGR2GRAY
        )


        clahe = cv2.createCLAHE(
            clipLimit=2.0,
            tileGridSize=(8, 8)
        )


        enhanced = clahe.apply(
            gray
        )


        enhanced = cv2.cvtColor(
            enhanced,
            cv2.COLOR_GRAY2BGR
        )


        variants["clahe"] = enhanced


        return variants


    # ========================================================
    # RUN OCR
    # ========================================================

    def run_ocr(self, image):

        results = self.ocr.predict(
            image
        )


        best_text = ""

        best_score = 0.0


        for result in results:

            data = result.json


            if callable(data):

                data = data()


            res = data.get(
                "res",
                {}
            )


            text = str(
                res.get(
                    "rec_text",
                    ""
                )
            ).strip()


            score = float(
                res.get(
                    "rec_score",
                    0.0
                )
            )


            if (
                text
                and score > best_score
            ):

                best_text = text

                best_score = score


        return (
            best_text,
            best_score
        )


    # ========================================================
    # CLEAN PLATE TEXT
    # ========================================================

    def clean_plate_text(self, text):

        text = str(
            text
        ).upper()


        # Remove spaces and special characters

        text = re.sub(
            r"[^A-Z0-9]",
            "",
            text
        )


        return text


    # ========================================================
    # OCR ONE REGION
    # ========================================================

    def recognize_region(self, image):

        variants = (
            self.create_ocr_variants(
                image
            )
        )


        results = []


        for name, variant in variants.items():

            text, score = (
                self.run_ocr(
                    variant
                )
            )


            text = (
                self.clean_plate_text(
                    text
                )
            )


            if text:

                results.append({
                    "variant": name,
                    "text": text,
                    "score": score
                })


        if not results:

            return "", 0.0


        best = max(
            results,
            key=lambda x: x["score"]
        )


        return (
            best["text"],
            best["score"]
        )


    # ========================================================
    # READ LICENSE PLATE
    # ========================================================

    def read_plate(self, plate_crop):

        if plate_crop is None:

            return (
                "",
                0.0
            )


        if plate_crop.size == 0:

            return (
                "",
                0.0
            )


        # ----------------------------------------------------
        # Rectify plate
        # ----------------------------------------------------

        rectified = (
            self.rectify_plate(
                plate_crop
            )
        )


        h, w = rectified.shape[:2]


        aspect_ratio = (
            w / h
        )


        # ----------------------------------------------------
        # Detect two-line plate
        # ----------------------------------------------------

        is_two_line = (
            aspect_ratio < 3.0
        )


        # ----------------------------------------------------
        # TWO-LINE PLATE
        # ----------------------------------------------------

        if is_two_line:

            margin_y = int(
                h * 0.05
            )


            usable = rectified[
                margin_y:
                h - margin_y,
                :
            ]


            usable_h = (
                usable.shape[0]
            )


            split = int(
                usable_h * 0.50
            )


            top_line = usable[
                :split,
                :
            ]


            bottom_line = usable[
                split:,
                :
            ]


            top_text, top_score = (
                self.recognize_region(
                    top_line
                )
            )


            bottom_text, bottom_score = (
                self.recognize_region(
                    bottom_line
                )
            )


            # ------------------------------------------------
            # Combine two lines
            # ------------------------------------------------

            if (
                top_text
                and bottom_text
            ):

                final_text = (
                    top_text
                    + bottom_text
                )


                final_score = (
                    top_score
                    + bottom_score
                ) / 2.0


                return (
                    final_text,
                    final_score
                )


            # If only one line succeeded

            if top_text:

                return (
                    top_text,
                    top_score
                )


            if bottom_text:

                return (
                    bottom_text,
                    bottom_score
                )


            return (
                "",
                0.0
            )


        # ----------------------------------------------------
        # SINGLE-LINE PLATE
        # ----------------------------------------------------

        text, score = (
            self.recognize_region(
                rectified
            )
        )


        return (
            text,
            score
        )


    # ========================================================
    # DETECT AND READ
    # ========================================================

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


                if (
                    detection_confidence
                    < 0.25
                ):

                    continue


                x1, y1, x2, y2 = map(
                    int,
                    box.xyxy[0].tolist()
                )


                # ------------------------------------------------
                # Add padding
                # ------------------------------------------------

                width = x2 - x1

                height = y2 - y1


                padding_x = int(
                    width * 0.08
                )

                padding_y = int(
                    height * 0.08
                )


                image_h, image_w = (
                    image.shape[:2]
                )


                x1p = max(
                    0,
                    x1 - padding_x
                )

                y1p = max(
                    0,
                    y1 - padding_y
                )

                x2p = min(
                    image_w,
                    x2 + padding_x
                )

                y2p = min(
                    image_h,
                    y2 + padding_y
                )


                plate_crop = image[
                    y1p:y2p,
                    x1p:x2p
                ]


                if plate_crop.size == 0:

                    continue


                # ------------------------------------------------
                # OCR
                # ------------------------------------------------

                plate_text, ocr_confidence = (
                    self.read_plate(
                        plate_crop
                    )
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