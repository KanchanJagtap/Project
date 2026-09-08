from ai.tracking.vehicle_tracker import VehicleTracker


class VehicleIntelligence:
    """
    Vehicle intelligence layer built on top of VehicleTracker.

    Responsibilities:
    - Track vehicles using YOLO + ByteTrack
    - Maintain per-vehicle history
    - Calculate movement direction
    - Track first/last seen frame
    - Track best confidence
    - Store trajectory
    """

    VEHICLE_CLASSES = VehicleTracker.VEHICLE_CLASSES

    def __init__(self):
        print("Loading vehicle detection model...")

        self.tracker = VehicleTracker()

        self.vehicles = {}

    def calculate_direction(self, trajectory):
        """
        Estimate vehicle movement direction from trajectory points.

        Returns:
            "down"
            "up"
            "right"
            "left"
            "stationary"
            "unknown"
        """

        if len(trajectory) < 2:
            return "unknown"

        first_x, first_y = trajectory[0]
        last_x, last_y = trajectory[-1]

        dx = last_x - first_x
        dy = last_y - first_y

        threshold = 5

        if abs(dx) < threshold and abs(dy) < threshold:
            return "stationary"

        if abs(dx) > abs(dy):
            if dx > 0:
                return "right"
            else:
                return "left"

        if dy > 0:
            return "down"

        return "up"

    def process_video(self, video_path):
        """
        Process a video using VehicleTracker.
        """

        print("\nStarting YOLO + ByteTrack...")
        print(f"Video: {video_path}\n")

        results = self.tracker.track_video(video_path)

        frame_count = 0

        for result in results:
            frame_count += 1

            if result.boxes is None:
                continue

            boxes = result.boxes

            if boxes.id is None:
                continue

            track_ids = boxes.id.int().cpu().tolist()
            class_ids = boxes.cls.int().cpu().tolist()
            confidences = boxes.conf.cpu().tolist()
            xyxy = boxes.xyxy.cpu().tolist()

            for track_id, class_id, confidence, bbox in zip(
                track_ids,
                class_ids,
                confidences,
                xyxy,
            ):
                if class_id not in self.VEHICLE_CLASSES:
                    continue

                vehicle_type = self.VEHICLE_CLASSES[class_id]

                x1, y1, x2, y2 = bbox

                center_x = (x1 + x2) / 2
                center_y = (y1 + y2) / 2

                center = (center_x, center_y)

                if track_id not in self.vehicles:
                    self.vehicles[track_id] = {
                        "id": track_id,
                        "type": vehicle_type,
                        "first_seen": frame_count,
                        "last_seen": frame_count,
                        "frames_tracked": 1,
                        "best_confidence": confidence,
                        "bbox": tuple(bbox),
                        "center": center,
                        "trajectory": [center],
                    }

                else:
                    vehicle = self.vehicles[track_id]

                    vehicle["last_seen"] = frame_count

                    vehicle["frames_tracked"] += 1

                    vehicle["best_confidence"] = max(
                        vehicle["best_confidence"],
                        confidence,
                    )

                    vehicle["bbox"] = tuple(bbox)

                    vehicle["center"] = center

                    vehicle["trajectory"].append(center)

                    vehicle["type"] = vehicle_type

            if frame_count % 25 == 0:
                print(
                    f"Processed frame {frame_count} | "
                    f"Unique vehicles: {len(self.vehicles)}"
                )

        print("\nProcessing complete.")
        print(f"Total frames: {frame_count}")

    def print_summary(self):
        """
        Print vehicle intelligence summary.
        """

        print("\n" + "=" * 60)
        print("VEHICLE INTELLIGENCE SUMMARY")
        print("=" * 60)

        print(f"Unique vehicles: {len(self.vehicles)}")

        counts = {
            "car": 0,
            "motorcycle": 0,
            "bus": 0,
            "truck": 0,
        }

        for vehicle in self.vehicles.values():
            vehicle_type = vehicle["type"]

            if vehicle_type in counts:
                counts[vehicle_type] += 1

        print("\nVehicle Types:")

        for vehicle_type, count in counts.items():
            print(f"  {vehicle_type}: {count}")

        print("\nSample Vehicle Records:")

        for vehicle_id, vehicle in list(self.vehicles.items())[:10]:

            direction = self.calculate_direction(
                vehicle["trajectory"]
            )

            print(
                f"\nVehicle ID: {vehicle_id}"
            )

            print(
                f"  Type: {vehicle['type']}"
            )

            print(
                f"  First seen: frame {vehicle['first_seen']}"
            )

            print(
                f"  Last seen: frame {vehicle['last_seen']}"
            )

            print(
                f"  Frames tracked: {vehicle['frames_tracked']}"
            )

            print(
                f"  Best confidence: "
                f"{vehicle['best_confidence']:.3f}"
            )

            print(
                f"  Direction: {direction}"
            )

            print(
                f"  Trajectory points: "
                f"{len(vehicle['trajectory'])}"
            )

        print("\n" + "=" * 60)


if __name__ == "__main__":
    video_path = "data/videos/traffic.mp4"

    intelligence = VehicleIntelligence()

    intelligence.process_video(video_path)

    intelligence.print_summary()