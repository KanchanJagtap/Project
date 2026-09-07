import cv2
import numpy as np
import re

from ultralytics import YOLO
from paddleocr import TextRecognition


# ============================================================
# CONFIGURATION
# ============================================================

IMAGE_PATH = "data/test/indian-plates/images/image_0025.jpg"

MODEL_PATH = "ai/models/license_plate.pt"

OUTPUT_RECTIFIED = (
    "data/test/indian-plates/plate_rectified_final.jpg"
)

OUTPUT_TOP = (
    "data/test/indian-plates/plate_top_final.jpg"
)

OUTPUT_BOTTOM = (
    "data/test/indian-plates/plate_bottom_final.jpg"
)


# ============================================================
# LOAD MODELS
# ============================================================

print("Loading license plate detector...")

detector = YOLO(
    MODEL_PATH
)


print("Loading OCR recognition model...")

ocr = TextRecognition(
    model_name="PP-OCRv6_medium_rec"
)


# ============================================================
# LOAD IMAGE
# ============================================================

print("Loading image...")

image = cv2.imread(
    IMAGE_PATH
)

if image is None:

    raise FileNotFoundError(
        IMAGE_PATH
    )


image_height, image_width = image.shape[:2]


print(
    "Image size:",
    image_width,
    "x",
    image_height
)


# ============================================================
# DETECT LICENSE PLATE
# ============================================================

print(
    "\nDetecting license plate..."
)


results = detector(
    image,
    verbose=False
)


if (
    not results
    or len(results[0].boxes) == 0
):

    print(
        "No license plate detected."
    )

    exit()


boxes = results[0].boxes


best_index = max(
    range(len(boxes)),
    key=lambda i: float(
        boxes[i].conf[0]
    )
)


box = boxes[best_index]


detection_confidence = float(
    box.conf[0]
)


x1, y1, x2, y2 = map(
    int,
    box.xyxy[0].tolist()
)


print(
    "Detection confidence:",
    detection_confidence
)


print(
    "YOLO BBox:",
    [x1, y1, x2, y2]
)


# ============================================================
# PAD YOLO CROP
# ============================================================

bbox_width = x2 - x1
bbox_height = y2 - y1


padding_x = int(
    bbox_width * 0.08
)

padding_y = int(
    bbox_height * 0.08
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
    image_width,
    x2 + padding_x
)

y2p = min(
    image_height,
    y2 + padding_y
)


plate_crop = image[
    y1p:y2p,
    x1p:x2p
]


if plate_crop.size == 0:

    raise RuntimeError(
        "Empty plate crop."
    )


crop_h, crop_w = plate_crop.shape[:2]


print(
    "Padded plate crop:",
    crop_w,
    "x",
    crop_h
)


# ============================================================
# FIND PLATE QUADRILATERAL
# ============================================================

def find_plate_corners(crop):

    gray = cv2.cvtColor(
        crop,
        cv2.COLOR_BGR2GRAY
    )


    candidates = []


    # Try multiple brightness thresholds.
    #
    # This is important because CCTV images can have:
    #
    # - shadows
    # - glare
    # - reflections
    # - different plate brightness
    #
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


        # Connect broken plate edges

        kernel = cv2.getStructuringElement(
            cv2.MORPH_RECT,
            (15, 15)
        )


        binary = cv2.morphologyEx(
            binary,
            cv2.MORPH_CLOSE,
            kernel
        )


        # Remove tiny noise

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


            # ------------------------------------------------
            # Calculate side lengths
            # ------------------------------------------------

            tl, tr, br, bl = order_points(
                points
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


            # Number plates should be wider
            # than they are tall.

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


            # Ignore extremely small objects

            if area_ratio < 0.20:
                continue


            # Prefer large plate-like regions.

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


    # Highest scoring candidate

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


# ============================================================
# ORDER POINTS
# ============================================================

def order_points(points):

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


# ============================================================
# FIND CORNERS
# ============================================================

print(
    "\nSearching for actual plate corners..."
)


plate_info = find_plate_corners(
    plate_crop
)


if plate_info is not None:

    corners = order_points(
        plate_info["points"]
    )


    print(
        "Plate quadrilateral FOUND."
    )


    print(
        "Threshold:",
        plate_info["threshold"]
    )


    print(
        "Plate aspect ratio:",
        round(
            plate_info["aspect_ratio"],
            2
        )
    )


    print(
        "Corners:"
    )


    print(
        corners
    )


else:

    print(
        "Plate quadrilateral NOT found."
    )


    print(
        "Using YOLO bounding box as fallback."
    )


    corners = np.float32([
        [0, 0],
        [crop_w - 1, 0],
        [crop_w - 1, crop_h - 1],
        [0, crop_h - 1]
    ])


# ============================================================
# PERSPECTIVE RECTIFICATION
# ============================================================

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


# Keep sufficient resolution for OCR

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
    [output_width - 1, output_height - 1],
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


# ============================================================
# SAVE RECTIFIED PLATE
# ============================================================

cv2.imwrite(
    OUTPUT_RECTIFIED,
    rectified
)


print(
    "\nSaved perspective-corrected plate:"
)


print(
    OUTPUT_RECTIFIED
)


print(
    "Rectified size:",
    output_width,
    "x",
    output_height
)


# ============================================================
# OCR PREPROCESSING
# ============================================================

def create_ocr_variants(image):

    variants = {}


    # --------------------------------------------------------
    # Original
    # --------------------------------------------------------

    variants["ORIGINAL"] = image


    # --------------------------------------------------------
    # Enlarged
    # --------------------------------------------------------

    enlarged = cv2.resize(
        image,
        None,
        fx=1.5,
        fy=1.5,
        interpolation=cv2.INTER_CUBIC
    )


    variants["ENLARGED"] = enlarged


    # --------------------------------------------------------
    # Sharpened
    # --------------------------------------------------------

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


    variants["SHARPENED"] = sharpened


    # --------------------------------------------------------
    # CLAHE
    # --------------------------------------------------------

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


    variants["CLAHE"] = enhanced


    # --------------------------------------------------------
    # Adaptive threshold
    # --------------------------------------------------------

    thresholded = cv2.adaptiveThreshold(
        gray,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        31,
        11
    )


    thresholded = cv2.cvtColor(
        thresholded,
        cv2.COLOR_GRAY2BGR
    )


    variants["ADAPTIVE"] = thresholded


    return variants


# ============================================================
# OCR FUNCTION
# ============================================================

def run_ocr(image):

    results = ocr.predict(
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


# ============================================================
# CLEAN OCR TEXT
# ============================================================

def clean_plate_text(text):

    text = str(
        text
    ).upper()


    # Remove spaces and punctuation

    text = re.sub(
        r"[^A-Z0-9]",
        "",
        text
    )


    return text


# ============================================================
# DETERMINE ONE-LINE / TWO-LINE
# ============================================================

rectified_height, rectified_width = (
    rectified.shape[:2]
)


rectified_ratio = (
    rectified_width
    / rectified_height
)


print(
    "\nRectified plate ratio:",
    round(
        rectified_ratio,
        2
    )
)


# A relatively short/wide plate is usually
# a two-line plate in this test.
#
# We deliberately keep this threshold broad.

is_two_line = (
    rectified_ratio < 3.0
)


if is_two_line:

    print(
        "Plate type: POSSIBLE TWO-LINE"
    )

else:

    print(
        "Plate type: POSSIBLE SINGLE-LINE"
    )


# ============================================================
# TWO-LINE PLATE PROCESSING
# ============================================================

if is_two_line:

    # Ignore a small border around the plate.

    margin_y = int(
        rectified_height * 0.05
    )


    usable = rectified[
        margin_y:
        rectified_height - margin_y,
        :
    ]


    usable_height = usable.shape[0]


    # Split around the middle.

    split = int(
        usable_height * 0.50
    )


    top_line = usable[
        :split,
        :
    ]


    bottom_line = usable[
        split:,
        :
    ]


    # Save line crops

    cv2.imwrite(
        OUTPUT_TOP,
        top_line
    )


    cv2.imwrite(
        OUTPUT_BOTTOM,
        bottom_line
    )


    print(
        "\nSaved top line:"
    )

    print(
        OUTPUT_TOP
    )


    print(
        "Saved bottom line:"
    )

    print(
        OUTPUT_BOTTOM
    )


    # --------------------------------------------------------
    # OCR TOP LINE
    # --------------------------------------------------------

    print(
        "\n========================================"
    )

    print(
        "OCR TOP LINE"
    )

    print(
        "========================================"
    )


    top_variants = create_ocr_variants(
        top_line
    )


    top_results = []


    for name, variant in top_variants.items():

        text, score = run_ocr(
            variant
        )


        text = clean_plate_text(
            text
        )


        print(
            f"{name}: {text} "
            f"(confidence={score:.4f})"
        )


        if text:

            top_results.append({
                "variant": name,
                "text": text,
                "score": score
            })


    # --------------------------------------------------------
    # OCR BOTTOM LINE
    # --------------------------------------------------------

    print(
        "\n========================================"
    )

    print(
        "OCR BOTTOM LINE"
    )

    print(
        "========================================"
    )


    bottom_variants = create_ocr_variants(
        bottom_line
    )


    bottom_results = []


    for name, variant in bottom_variants.items():

        text, score = run_ocr(
            variant
        )


        text = clean_plate_text(
            text
        )


        print(
            f"{name}: {text} "
            f"(confidence={score:.4f})"
        )


        if text:

            bottom_results.append({
                "variant": name,
                "text": text,
                "score": score
            })


    # --------------------------------------------------------
    # SELECT BEST TOP/BOTTOM
    # --------------------------------------------------------

    best_top = None

    best_bottom = None


    if top_results:

        best_top = max(
            top_results,
            key=lambda x: x["score"]
        )


    if bottom_results:

        best_bottom = max(
            bottom_results,
            key=lambda x: x["score"]
        )


    print(
        "\n========================================"
    )

    print(
        "BEST TWO-LINE RESULT"
    )

    print(
        "========================================"
    )


    if best_top:

        print(
            "Top:",
            best_top["text"]
        )

        print(
            "Top confidence:",
            best_top["score"]
        )

    else:

        print(
            "Top: No result"
        )


    if best_bottom:

        print(
            "Bottom:",
            best_bottom["text"]
        )

        print(
            "Bottom confidence:",
            best_bottom["score"]
        )

    else:

        print(
            "Bottom: No result"
        )


    if (
        best_top
        and best_bottom
    ):

        final_text = (
            best_top["text"]
            + best_bottom["text"]
        )


        average_confidence = (
            best_top["score"]
            + best_bottom["score"]
        ) / 2


        print(
            "\nFINAL PLATE:"
        )

        print(
            final_text
        )


        print(
            "Average OCR confidence:",
            average_confidence
        )


# ============================================================
# SINGLE-LINE PLATE PROCESSING
# ============================================================

else:

    print(
        "\n========================================"
    )

    print(
        "OCR SINGLE-LINE PLATE"
    )

    print(
        "========================================"
    )


    variants = create_ocr_variants(
        rectified
    )


    results = []


    for name, variant in variants.items():

        text, score = run_ocr(
            variant
        )


        text = clean_plate_text(
            text
        )


        print(
            f"{name}: {text} "
            f"(confidence={score:.4f})"
        )


        if text:

            results.append({
                "variant": name,
                "text": text,
                "score": score
            })


    print(
        "\n========================================"
    )

    print(
        "BEST SINGLE-LINE RESULT"
    )

    print(
        "========================================"
    )


    if results:

        best = max(
            results,
            key=lambda x: x["score"]
        )


        print(
            "Text:",
            best["text"]
        )


        print(
            "Variant:",
            best["variant"]
        )


        print(
            "Confidence:",
            best["score"]
        )

    else:

        print(
            "No OCR result."
        )


# ============================================================
# COMPLETE
# ============================================================

print(
    "\n========================================"
)

print(
    "ANPR TEST COMPLETE"
)

print(
    "========================================"
)