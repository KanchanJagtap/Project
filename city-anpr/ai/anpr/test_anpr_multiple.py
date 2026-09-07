import cv2
from anpr_pipeline import ANPRPipeline


IMAGE_PATH = "data/test/indian-plates/images/image_0025.jpg"


def main():

    print("\n===== ANPR MULTIPLE IMAGE TEST =====")

    image = cv2.imread(IMAGE_PATH)

    if image is None:
        print("ERROR: Could not load image.")
        return

    print(f"Image: {IMAGE_PATH}")
    print(
        f"Size: "
        f"{image.shape[1]} x {image.shape[0]}"
    )

    anpr = ANPRPipeline()

    detections = anpr.detect_and_read(image)

    print("\n===== RESULTS =====")

    for i, plate in enumerate(detections, start=1):

        print(f"\nPlate #{i}")

        print(
            f"Text: '{plate['text']}'"
        )

        print(
            f"Detection confidence: "
            f"{plate['detection_confidence']:.2f}"
        )

        print(
            f"OCR confidence: "
            f"{plate['ocr_confidence']:.2f}"
        )

        print(
            f"BBox: {plate['bbox']}"
        )

    if not detections:
        print("No plates detected.")

    print("\n====================\n")


if __name__ == "__main__":
    main()