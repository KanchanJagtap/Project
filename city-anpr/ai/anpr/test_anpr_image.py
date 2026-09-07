import cv2
from anpr_pipeline import ANPRPipeline


def main():

    image_path = "data/test/indian-plates/images/image_0032.jpg"

    print("\n===== CITY ANPR PIPELINE TEST =====")
    print(f"Image: {image_path}")

    image = cv2.imread(image_path)

    if image is None:
        print("ERROR: Could not load image.")
        return

    print(
        f"Image size: "
        f"{image.shape[1]} x {image.shape[0]}"
    )

    anpr = ANPRPipeline()

    print("\nDetecting and reading license plates...")

    detections = anpr.detect_and_read(image)

    print("\n===== ANPR RESULTS =====")

    if not detections:
        print("No license plates detected.")

    for i, plate in enumerate(detections, start=1):

        print(f"Plate #{i}")

        print(
            f"  Text: "
            f"'{plate['text']}'"
        )

        print(
            f"  Detection confidence: "
            f"{plate['detection_confidence']:.2f}"
        )

        print(
            f"  OCR confidence: "
            f"{plate['ocr_confidence']:.2f}"
        )

        print(
            f"  BBox: "
            f"{plate['bbox']}"
        )

    print("=============================\n")


if __name__ == "__main__":
    main()