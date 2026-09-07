import cv2
from ultralytics import YOLO


IMAGE_PATH = "data/test/indian-plates/images/image_0032.jpg"
OUTPUT_PATH = "data/test/detected_plate.jpg"


def main():

    image = cv2.imread(IMAGE_PATH)

    if image is None:
        print("ERROR: Could not load image.")
        return

    model = YOLO("ai/models/license_plate.pt")

    results = model(
        image,
        verbose=False
    )

    best_box = None
    best_confidence = 0

    for result in results:

        for box in result.boxes:

            confidence = float(box.conf[0])

            if confidence > best_confidence:

                best_confidence = confidence

                best_box = [
                    int(x)
                    for x in box.xyxy[0].tolist()
                ]

    if best_box is None:
        print("No license plate detected.")
        return

    x1, y1, x2, y2 = best_box

    plate = image[y1:y2, x1:x2]

    cv2.imwrite(
        OUTPUT_PATH,
        plate
    )

    print("\n===== DETECTED PLATE =====")
    print(f"Confidence: {best_confidence:.2f}")
    print(f"BBox: {best_box}")
    print(
        f"Crop size: "
        f"{plate.shape[1]} x {plate.shape[0]}"
    )
    print(f"Saved: {OUTPUT_PATH}")
    print("==========================\n")


if __name__ == "__main__":
    main()