import cv2
from paddleocr import PaddleOCR


IMAGE_PATH = "data/test/indian-plates/images/image_0025.jpg"

# Coordinates returned by your plate detector
X1, Y1, X2, Y2 = 920, 633, 2937, 1787


print("=" * 60)
print("OCR DIAGNOSTIC TEST")
print("=" * 60)

image = cv2.imread(IMAGE_PATH)

if image is None:
    raise FileNotFoundError(f"Could not load image: {IMAGE_PATH}")

print(f"Original image size: {image.shape[1]} x {image.shape[0]}")

# ---------------------------------------------------------
# 1. Extract detected plate
# ---------------------------------------------------------

plate = image[Y1:Y2, X1:X2]

if plate.size == 0:
    raise ValueError("Plate crop is empty")

print(f"Plate crop size: {plate.shape[1]} x {plate.shape[0]}")

cv2.imwrite(
    "data/test/indian-plates/ocr_raw_crop.jpg",
    plate
)

# ---------------------------------------------------------
# 2. Create enlarged crop
# ---------------------------------------------------------

scale = 2.0

large = cv2.resize(
    plate,
    None,
    fx=scale,
    fy=scale,
    interpolation=cv2.INTER_CUBIC
)

cv2.imwrite(
    "data/test/indian-plates/ocr_enlarged.jpg",
    large
)

# ---------------------------------------------------------
# 3. Grayscale
# ---------------------------------------------------------

gray = cv2.cvtColor(
    large,
    cv2.COLOR_BGR2GRAY
)

cv2.imwrite(
    "data/test/indian-plates/ocr_gray.jpg",
    gray
)

# ---------------------------------------------------------
# 4. CLAHE
# ---------------------------------------------------------

clahe = cv2.createCLAHE(
    clipLimit=2.0,
    tileGridSize=(8, 8)
)

clahe_image = clahe.apply(gray)

cv2.imwrite(
    "data/test/indian-plates/ocr_clahe.jpg",
    clahe_image
)

# ---------------------------------------------------------
# 5. Initialize PaddleOCR
# ---------------------------------------------------------

print("\nLoading PaddleOCR...")

ocr = PaddleOCR(
    lang="en"
)

print("PaddleOCR ready.")

# ---------------------------------------------------------
# OCR helper
# ---------------------------------------------------------

def run_ocr(name, image):

    print("\n" + "-" * 60)
    print(f"OCR VARIANT: {name}")
    print("-" * 60)

    try:

        results = ocr.predict(image)

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

            for text, score in zip(texts, scores):

                print(
                    f"Text: {text} | "
                    f"Confidence: {float(score):.4f}"
                )

                found = True

        if not found:
            print("No text detected.")

    except Exception as e:

        print(f"OCR ERROR: {e}")


# ---------------------------------------------------------
# Run all variants
# ---------------------------------------------------------

run_ocr(
    "RAW PLATE",
    plate
)

run_ocr(
    "ENLARGED",
    large
)

run_ocr(
    "GRAYSCALE",
    gray
)

run_ocr(
    "CLAHE",
    clahe_image
)

print("\n" + "=" * 60)
print("OCR DIAGNOSTIC COMPLETE")
print("=" * 60)