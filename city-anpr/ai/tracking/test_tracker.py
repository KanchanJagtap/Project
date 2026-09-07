from vehicle_tracker import VehicleTracker


def main():
    tracker = VehicleTracker()

    video_path = "data/videos/traffic.mp4"

    print("\n===== CITY ANPR VEHICLE TRACKER =====")
    print("Starting vehicle tracking...")
    print("=====================================\n")

    results = tracker.track_video(video_path)

    total_frames = 0
    total_vehicles = 0

    for result in results:
        total_frames += 1

        if result.boxes is None:
            continue

        if result.boxes.id is None:
            continue

        track_ids = result.boxes.id.int().cpu().tolist()

        total_vehicles += len(track_ids)

        print(
            f"Frame {total_frames:03d} | "
            f"Vehicle IDs: {track_ids}"
        )

    print("\n===== TRACKING COMPLETE =====")
    print(f"Frames processed: {total_frames}")
    print(f"Vehicle detections: {total_vehicles}")
    print("=============================\n")


if __name__ == "__main__":
    main()