from ultralytics import YOLO


class VehicleIntelligence:
    """
    Vehicle detection + tracking + movement intelligence.

    Provides:
    - Persistent Track ID
    - Vehicle type
    - First/last seen frame
    - Frames tracked
    - Best confidence
    - Bounding box
    - Center position
    - Trajectory
    - Movement direction
    - X/Y movement
    """

    VEHICLE_CLASSES = {
        2: "car",
        3: "motorcycle",
        5: "bus",
        7: "truck",
    }

    def __init__(self, model_path="yolo11n.pt"):

        print("Loading vehicle detection model...")

        self.model = YOLO(model_path)

        self.vehicles = {}

    def calculate_direction(self, trajectory):

        if len(trajectory) < 2:
            return "UNKNOWN"

        start_x, start_y = trajectory[0]
        end_x, end_y = trajectory[-1]

        dx = end_x - start_x
        dy = end_y - start_y

        # Ignore extremely small movement
        if abs(dx) < 10 and abs(dy) < 10:
            return "STATIONARY"

        # Determine dominant movement axis
        if abs(dx) >= abs(dy):

            if dx > 0:
                return "RIGHT"

            return "LEFT"

        else:

            if dy > 0:
                return "DOWN"

            return "UP"

    def process_video(self, video_path):

        print(f"\nProcessing video: {video_path}")
        print("Starting YOLO + ByteTrack...\n")

        results = self.model.track(
            source=video_path,
            tracker="bytetrack.yaml",
            classes=list(self.VEHICLE_CLASSES.keys()),
            persist=True,
            stream=True,
            verbose=False,
        )

        frame_number = 0

        for result in results:

            frame_number += 1

            if result.boxes is None:
                continue

            boxes = result.boxes

            for i in range(len(boxes)):

                class_id = int(boxes.cls[i])

                confidence = float(boxes.conf[i])

                if class_id not in self.VEHICLE_CLASSES:
                    continue

                if boxes.id is None:
                    continue

                vehicle_type = self.VEHICLE_CLASSES[class_id]

                track_id = int(boxes.id[i])

                x1, y1, x2, y2 = map(
                    int,
                    boxes.xyxy[i].tolist()
                )

                # Center point
                center_x = int((x1 + x2) / 2)
                center_y = int((y1 + y2) / 2)

                center = [center_x, center_y]

                # New track
                if track_id not in self.vehicles:

                    self.vehicles[track_id] = {
                        "id": track_id,
                        "type": vehicle_type,
                        "first_seen": frame_number,
                        "last_seen": frame_number,
                        "frames_tracked": 1,
                        "best_confidence": confidence,
                        "bbox": [x1, y1, x2, y2],
                        "center": center,
                        "trajectory": [center],
                    }

                # Existing track
                else:

                    vehicle = self.vehicles[track_id]

                    vehicle["last_seen"] = frame_number

                    vehicle["frames_tracked"] += 1

                    vehicle["best_confidence"] = max(
                        vehicle["best_confidence"],
                        confidence
                    )

                    vehicle["bbox"] = [
                        x1,
                        y1,
                        x2,
                        y2,
                    ]

                    vehicle["center"] = center

                    vehicle["trajectory"].append(center)

        self.print_summary(frame_number)

    def print_summary(self, frame_number):

        print("\n" + "=" * 70)
        print("VEHICLE INTELLIGENCE V3 SUMMARY")
        print("=" * 70)

        print(f"\nFrames processed: {frame_number}")

        print(
            f"Unique tracked IDs: "
            f"{len(self.vehicles)}"
        )

        # Vehicle type statistics
        type_counts = {
            "car": 0,
            "motorcycle": 0,
            "bus": 0,
            "truck": 0,
        }

        for vehicle in self.vehicles.values():

            vehicle_type = vehicle["type"]

            if vehicle_type in type_counts:
                type_counts[vehicle_type] += 1

        print("\nVehicle type counts:")

        for vehicle_type, count in type_counts.items():

            print(
                f"  {vehicle_type}: {count}"
            )

        # Detailed movement information
        print("\nVehicle movement details:\n")

        for vehicle_id in sorted(self.vehicles):

            vehicle = self.vehicles[vehicle_id]

            trajectory = vehicle["trajectory"]

            start_position = trajectory[0]

            end_position = trajectory[-1]

            direction = self.calculate_direction(
                trajectory
            )

            dx = end_position[0] - start_position[0]

            dy = end_position[1] - start_position[1]

            print(
                f"ID: {vehicle['id']} | "
                f"Type: {vehicle['type']} | "
                f"Direction: {direction} | "
                f"Frames: {vehicle['frames_tracked']} | "
                f"Best Conf: {vehicle['best_confidence']:.2f}"
            )

            print(
                f"    Start: {start_position} | "
                f"End: {end_position} | "
                f"Movement: dx={dx}, dy={dy}"
            )

        print("\n" + "=" * 70)
        print("VEHICLE INTELLIGENCE V3 COMPLETE")
        print("=" * 70)


if __name__ == "__main__":

    video_path = "data/videos/traffic.mp4"

    intelligence = VehicleIntelligence()

    intelligence.process_video(video_path)