import cv2
from paddleocr import PaddleOCR


def main():
    video_path = "data/videos/traffic.mp4"

    print("\n===== CITY ANPR OCR TEST =====")

    # Open the traffic video
    cap = cv2.VideoCapture(video_path)

    if not cap.isOpened():
        print("ERROR: Could not open video.")
        return

    # Read the first frame
    success, frame = cap.read()
    cap.release()

    if not success:
        print("ERROR: Could not read video frame.")
        return

    print("Frame captured successfully.")
    print(f"Frame size: {frame.shape[1]} x {frame.shape[0]}")

    # Create OCR engine
    print("Loading PaddleOCR...")

    ocr = PaddleOCR(
        lang="en"
    )

    print("Running OCR...")

    # Run OCR on the frame
    results = ocr.predict(frame)

    print("\n===== OCR RESULTS =====")

    found_text = False

    for result in results:
        data = result.json

        if callable(data):
            data = data()

        print(data)

        found_text = True

    if not found_text:
        print("No text detected.")

    print("=======================\n")


if __name__ == "__main__":
    main()