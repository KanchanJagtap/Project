import cv2
from vehicle_tracker import VehicleTracker


def main():

    input_video = "data/videos/traffic.mp4"
    output_video = "data/videos/tracked_output.mp4"

    print("\n===== CITY ANPR TRACKING VIDEO =====")
    print("Input :", input_video)
    print("Output:", output_video)

    # Get video properties
    cap = cv2.VideoCapture(input_video)

    if not cap.isOpened():
        print("ERROR: Could not open input video.")
        return

    fps = cap.get(cv2.CAP_PROP_FPS)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    cap.release()

    # Create output video
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")

    writer = cv2.VideoWriter(
        output_video,
        fourcc,
        fps,
        (width, height)
    )

    tracker = VehicleTracker()

    results = tracker.track_video(input_video)

    frame_count = 0

    for result in results:

        # Draw bounding boxes, vehicle labels and tracking IDs
        annotated_frame = result.plot()

        writer.write(annotated_frame)

        frame_count += 1

        print(f"Processed frame {frame_count}/{251}")

    writer.release()

    print("\n===== COMPLETE =====")
    print(f"Frames processed: {frame_count}")
    print(f"Saved video: {output_video}")
    print("====================\n")


if __name__ == "__main__":
    main()