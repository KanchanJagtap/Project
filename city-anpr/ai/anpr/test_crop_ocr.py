import cv2
from paddleocr import PaddleOCR


IMAGE_PATH = "data/test/detected_plate.jpg"


def main():

    print("\n===== PLATE OCR TEST =====")

    image = cv2.imread(IMAGE_PATH)

    if image is None:
        print("ERROR: Could not load plate.")
        return

    print(
        f"Crop size: "
        f"{image.shape[1]} x {image.shape[0]}"
    )

    print("\nLoading PaddleOCR...")

    ocr = PaddleOCR(
        lang="en",
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=False
    )

    print("Running OCR...")

    results = ocr.predict(image)

    print("\n===== OCR RESULTS =====")

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

            text = str(text).strip()
            score = float(score)

            if text:

                print(
                    f"Text: '{text}' "
                    f"| Confidence: {score:.2f}"
                )

                found = True

    if not found:
        print("No text detected.")

    print("=========================\n")


if __name__ == "__main__":
    main()