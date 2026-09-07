"""Synthetic validation for the prototype dictionary adapters."""

import unittest

from ai.contracts.adapters import (
    UnmappedTrackingMetadataError,
    UnsupportedVehicleTypeError,
    detection_from_dict,
    tracked_vehicle_from_dict,
)


class ContractAdapterTests(unittest.TestCase):
    def test_detection_mapping(self):
        detection = detection_from_dict(
            {"class": "bus", "confidence": 0.91, "bbox": [1, 2, 30, 40]},
            camera_id="cam-01",
            frame_number=12,
        )

        self.assertEqual(detection.vehicle_type, "bus")
        self.assertEqual(detection.bbox, (1.0, 2.0, 30.0, 40.0))
        self.assertEqual(detection.frame_number, 12)

    def test_tracking_mapping_preserves_existing_metadata(self):
        vehicle = tracked_vehicle_from_dict(
            {
                "id": 42,
                "type": "car",
                "first_seen": 10,
                "last_seen": 25,
                "frames_tracked": 16,
                "best_confidence": 0.94,
                "confidence": 0.81,
                "bbox": [10, 20, 100, 200],
                "center": [55, 110],
                "trajectory": [[50, 100], [55, 110]],
                "type_history": ["car", "car"],
            },
            camera_id="cam-01",
        )

        self.assertEqual(vehicle.track_id, 42)
        self.assertEqual(vehicle.vehicle_type, "car")
        self.assertEqual(vehicle.first_seen_frame, 10)
        self.assertEqual(vehicle.last_seen_frame, 25)
        self.assertEqual(vehicle.frames_tracked, 16)
        self.assertEqual(vehicle.best_confidence, 0.94)
        self.assertEqual(vehicle.center, (55.0, 110.0))
        self.assertEqual(vehicle.trajectory, [(50.0, 100.0), (55.0, 110.0)])
        self.assertEqual(vehicle.type_history, ["car", "car"])

    def test_unsupported_type_is_explicit(self):
        with self.assertRaises(UnsupportedVehicleTypeError):
            detection_from_dict(
                {"class": "person", "confidence": 0.8, "bbox": [0, 0, 1, 1]}
            )

    def test_unknown_tracking_field_is_not_silently_discarded(self):
        with self.assertRaises(UnmappedTrackingMetadataError):
            tracked_vehicle_from_dict(
                {
                    "id": 1,
                    "type": "car",
                    "bbox": [0, 0, 1, 1],
                    "best_confidence": 0.9,
                    "unmapped_field": "preserve me",
                }
            )


if __name__ == "__main__":
    unittest.main()
