from ultralytics import YOLO


class VehicleTracker:
    """
    Detects and tracks vehicles using YOLO + ByteTrack.
    """

    VEHICLE_CLASSES = {
        2: "car",
        3: "motorcycle",
        5: "bus",
        7: "truck",
    }

    def __init__(
        self,
        model_path="runs/detect/runs/cctv/uvh26_80ep-2/weights/best.pt",
    ):
        self.model = YOLO(model_path)

    def track_video(self, video_path):
        """
        Track vehicles in a video using ByteTrack.
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