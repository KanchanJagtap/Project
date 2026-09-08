from ultralytics import YOLO


class VehicleTracker:
    """
    Detects and tracks vehicles using the custom UVH26 YOLO model
    + ByteTrack.

    UVH26 model classes:
        0  Hatchback
        1  Sedan
        2  SUV
        3  MUV
        4  Bus
        5  Truck
        6  Three-wheeler
        7  Two-wheeler
        8  LCV
        9  Mini-bus
        10 Tempo-traveller
        11 Bicycle
        12 Van
        13 Others

    The tracker converts UVH26-specific classes into the canonical
    vehicle types used by the rest of the City-Wide AI Engine:
        motorcycle
        car
        auto
        bus
        truck
    """

    # UVH26 class ID -> canonical vehicle type
    VEHICLE_CLASSES = {
        0: "car",          # Hatchback
        1: "car",          # Sedan
        2: "car",          # SUV
        3: "car",          # MUV
        4: "bus",          # Bus
        5: "truck",        # Truck
        6: "auto",         # Three-wheeler
        7: "motorcycle",   # Two-wheeler
        8: "truck",        # LCV
        9: "bus",          # Mini-bus
        10: "bus",         # Tempo-traveller
        12: "car",         # Van
    }

    # Original UVH26 class names.
    UVH26_CLASS_NAMES = {
        0: "Hatchback",
        1: "Sedan",
        2: "SUV",
        3: "MUV",
        4: "Bus",
        5: "Truck",
        6: "Three-wheeler",
        7: "Two-wheeler",
        8: "LCV",
        9: "Mini-bus",
        10: "Tempo-traveller",
        11: "Bicycle",
        12: "Van",
        13: "Others",
    }

    # Classes intentionally excluded from vehicle tracking.
    EXCLUDED_CLASSES = {
        11,  # Bicycle
        13,  # Others
    }

    def __init__(
        self,
        model_path="runs/detect/runs/cctv/uvh26_80ep-2/weights/best.pt",
    ):
        """
        Load the custom UVH26 vehicle detection model.
        """
        self.model_path = model_path
        self.model = YOLO(model_path)

        print(f"Vehicle tracker model loaded: {model_path}")

    def track_video(self, video_path):
        """
        Track vehicles in a video using YOLO + ByteTrack.

        Only supported UVH26 vehicle classes are passed to the
        tracker. Bicycle and Others are excluded.
        """

        results = self.model.track(
            source=video_path,
            tracker="bytetrack.yaml",
            classes=list(self.VEHICLE_CLASSES.keys()),
            persist=True,
            stream=True,
            verbose=False,
        )

        return results

    def get_canonical_vehicle_type(self, class_id):
        """
        Convert a UVH26 class ID into the canonical vehicle type.
        """

        class_id = int(class_id)

        if class_id not in self.VEHICLE_CLASSES:
            return None

        return self.VEHICLE_CLASSES[class_id]

    def get_original_class_name(self, class_id):
        """
        Return the original UVH26 class name.
        """

        class_id = int(class_id)

        return self.UVH26_CLASS_NAMES.get(
            class_id,
            "Unknown",
        )


if __name__ == "__main__":
    print("\n===== VEHICLE TRACKER MODEL TEST =====")

    tracker = VehicleTracker()

    print("\nUVH26 -> Canonical mapping:")

    for class_id, vehicle_type in tracker.VEHICLE_CLASSES.items():
        original_name = tracker.get_original_class_name(class_id)

        print(
            f"  {class_id:2d} "
            f"{original_name:18s} -> "
            f"{vehicle_type}"
        )

    print("\nExcluded classes:")

    for class_id in sorted(tracker.EXCLUDED_CLASSES):
        print(
            f"  {class_id:2d} "
            f"{tracker.get_original_class_name(class_id)}"
        )

    print("\n===== TEST PASSED =====")