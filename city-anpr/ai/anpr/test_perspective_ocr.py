import cv2
import numpy as np
from paddleocr import PaddleOCR

IMAGE_PATH = "data/test/indian-plates/images/image_0025.jpg"

print("=" * 60)
print("PERSPECTIVE CORRECTION + OCR TEST")
print("=" * 60)

image = cv2.imread(IMAGE_PATH)

if image is None:
    raise FileNotFoundError(IMAGE_PATH)

print("Original:", image.shape[1], "x", image.shape[0])

# ---------------------------------------------------------
# Approximate four corners of the actual license plate
# Based on the detected plate in image_0025.jpg
#
# Order:
# top-left -> top-right -> bottom-right -> bottom-left
# ---------------------------------------------------------

src = np.float32([
    [850, 760],
    [2920, 650],
    [2910, 1540],
    [870, 1710],
])

# ---------------------------------------------------------
# Destination rectangle
# ---------------------------------------------------------

width = 2000
height = 850

dst = np.float32([
    [0, 0],
    [width - 1, 0],
    [width - 1, height - 1],
    [0, height - 1],
])

# ---------------------------------------------------------
# Perspective transformation
# ---------------------------------------------------------

matrix = cv2.getPerspectiveTransform(src, dst)

rectified = cv2.warpPerspective(
    image,
    matrix,
    (width, height)
)

cv2.imwrite(
    "data/test/indian-plates/plate_rectified.jpg",
    rectified
)

print(
    "Saved:",
    "data/test/indian-plates/plate_rectified.jpg"
)

# ---------------------------------------------------------
# Crop a little border
# ---------------------------------------------------------

h, w = rectified.shape[:2]

cropped = rectified[
    int(h * 0.08):int(h * 0.92),
    int(w * 0.03):int(w * 0.97)
]

cv2.imwrite(
    "data/test/indian-plates/plate_rectified_crop.jpg",
    cropped
)

# ---------------------------------------------------------
# Resize while staying below PaddleOCR limit
# ---------------------------------------------------------

h, w = cropped.shape[:2]

max_side = max(h, w)

if max_side > 3800:

    scale = 3800 / max_side

    cropped = cv2.resize(
        cropped,
        (
            int(w * scale),
            int(h * scale)
        ),
        interpolation=cv2.INTER_CUBIC
    )

# ---------------------------------------------------------
# Enhancement
# ---------------------------------------------------------

gray = cv2.cvtColor(
    cropped,
    cv2.COLOR_BGR2GRAY
)

clahe = cv2.createCLAHE(
    clipLimit=2.0,
    tileGridSize=(8, 8)
)

enhanced_gray = clahe.apply(gray)

# IMPORTANT:
# Convert back to 3 channels before PaddleOCR

enhanced = cv2.cvtColor(
    enhanced_gray,
    cv2.COLOR_GRAY2BGR
)

cv2.imwrite(
    "data/test/indian-plates/plate_enhanced.jpg",
    enhanced
)

# ---------------------------------------------------------
# PaddleOCR
# ---------------------------------------------------------

print("\nLoading PaddleOCR...")

ocr = PaddleOCR(
    lang="en"
)

print("PaddleOCR ready.")

# ---------------------------------------------------------
# OCR function
# ---------------------------------------------------------

def run_ocr(name, img):

    print("\n" + "-" * 60)
    print("OCR:", name)
    print("-" * 60)

    try:

        results = ocr.predict(img)

        found = False

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

                print(
                    "Text:",
                    repr(str(text)),
                    "| Confidence:",
                    round(float(score), 4)
                )

                found = True

        if not found:
            print("No text detected.")

    except Exception as e:

        print("OCR ERROR:", repr(e))


# ---------------------------------------------------------
# Test rectified original
# ---------------------------------------------------------

run_ocr(
    "RECTIFIED",
    cropped
)

# ---------------------------------------------------------
# Test enhanced rectified
# ---------------------------------------------------------

run_ocr(
    "RECTIFIED + CLAHE",
    enhanced
)

print("\n" + "=" * 60)
print("TEST COMPLETE")
print("=" * 60)