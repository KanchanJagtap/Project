import cv2
from ultralytics import YOLO


def main():

    video_path = "data/videos/traffic.mp4"
    output_path = "data/test/plate_crop_frame180.jpg"

    print("\n===== SAVE PLATE CROP =====")

    cap = cv2.VideoCapture(video_path)

    if not cap.isOpened():
        print("ERROR: Could not open video.")
        return

    # Frame 180
    cap.set(cv2.CAP_PROP_POS_FRAMES, 180)

    success, frame = cap.read()
    cap.release()

    if not success:
        print("ERROR: Could not read frame 180.")
        return

    model = YOLO(
        "ai/models/license_plate.pt"
    )

    results = model(
        frame,
        verbose=False
    )

    best_plate = None
    best_confidence = 0

    for result in results:

        for box in result.boxes:

            confidence = float(box.conf[0])

            if confidence > best_confidence:

                best_confidence = confidence

                x1, y1, x2, y2 = map(
                    int,
                    box.xyxy[0].tolist()
                )

                best_plate = (
                    x1,
                    y1,
                    x2,
                    y2
                )

    if best_plate is None:
        print("No plate detected.")
        return

    x1, y1, x2, y2 = best_plate

    # Add margin
    margin_x = int((x2 - x1) * 0.15)
    margin_y = int((y2 - y1) * 0.25)

    x1 = max(0, x1 - margin_x)
    y1 = max(0, y1 - margin_y)
    x2 = min(frame.shape[1], x2 + margin_x)
    y2 = min(frame.shape[0], y2 + margin_y)

    plate = frame[
        y1:y2,
        x1:x2
    ]

    # Enlarge for inspection
    plate = cv2.resize(
        plate,
        None,
        fx=8,
        fy=8,
        interpolation=cv2.INTER_CUBIC
    )

    cv2.imwrite(
        output_path,
        plate
    )

    print(f"Confidence: {best_confidence:.2f}")
    print(f"Saved: {output_path}")
    print("===========================\n")


if __name__ == "__main__":
    main()