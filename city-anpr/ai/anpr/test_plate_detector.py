import cv2
from plate_detector import LicensePlateDetector


def main():

    video_path = "data/videos/traffic.mp4"

    print("\n===== LICENSE PLATE DETECTOR VIDEO TEST =====")

    cap = cv2.VideoCapture(video_path)

    if not cap.isOpened():
        print("ERROR: Could not open video.")
        return

    # Check several frames instead of only the first frame
    detector = LicensePlateDetector()

    frame_number = 0
    total_plates = 0

    while True:

        success, frame = cap.read()

        if not success:
            break

        frame_number += 1

        # Test every 10th frame
        if frame_number % 10 != 0:
            continue

        plates = detector.detect(frame)

        print(
            f"Frame {frame_number:03d} | "
            f"Plates detected: {len(plates)}"
        )

        total_plates += len(plates)

        for i, plate in enumerate(plates, start=1):
            print(
                f"    Plate #{i} | "
                f"Confidence: {plate['confidence']:.2f} | "
                f"BBox: {plate['bbox']}"
            )

    cap.release()

    print("\n===== TEST COMPLETE =====")
    print(f"Frames checked: {frame_number // 10}")
    print(f"Total plate detections: {total_plates}")
    print("=========================\n")


if __name__ == "__main__":
    main()