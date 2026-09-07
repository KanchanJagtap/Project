"""Synthetic geometry tests for same-frame plate-to-vehicle association."""

import unittest

from ai.contracts.association import associate_plates_to_vehicles
from ai.contracts.models import PlateObservation, TrackedVehicle


def vehicle(track_id, bbox, *, camera_id="cam-01", frame_number=10):
    return TrackedVehicle(
        track_id=track_id,
        vehicle_type="car",
        bbox=bbox,
        confidence=0.9,
        first_seen_frame=1,
        last_seen_frame=frame_number,
        camera_id=camera_id,
    )


def plate(bbox, *, camera_id="cam-01", frame_number=10, **kwargs):
    return PlateObservation(
        plate_text="MH12AB1234",
        detection_confidence=0.91,
        ocr_confidence=0.82,
        bbox=bbox,
        camera_id=camera_id,
        frame_number=frame_number,
        **kwargs,
    )


class AssociationTests(unittest.TestCase):
    def test_clear_plate_inside_vehicle_is_associated(self):
        result = associate_plates_to_vehicles(
            [vehicle(1, (0, 0, 100, 100))], [plate((30, 40, 70, 60))]
        )[0]

        self.assertEqual(result.track_id, 1)
        self.assertEqual(result.vehicle_bbox, (0.0, 0.0, 100.0, 100.0))
        self.assertEqual(result.association_confidence, 1.0)

    def test_plate_outside_all_vehicles_remains_unassociated(self):
        source = plate((120, 120, 140, 140))
        result = associate_plates_to_vehicles([vehicle(1, (0, 0, 100, 100))], [source])[0]

        self.assertIsNone(result.track_id)
        self.assertIsNone(result.association_confidence)

    def test_overlapping_vehicles_select_highest_coverage(self):
        result = associate_plates_to_vehicles(
            [vehicle(1, (0, 0, 55, 100)), vehicle(2, (0, 0, 100, 100))],
            [plate((40, 40, 80, 60))],
            vehicle_bbox_expansion=0.0,
        )[0]

        self.assertEqual(result.track_id, 2)
        self.assertEqual(result.association_confidence, 1.0)

    def test_coverage_below_threshold_remains_unassociated(self):
        result = associate_plates_to_vehicles(
            [vehicle(1, (0, 0, 10, 10))],
            [plate((5, 0, 15, 10))],
            minimum_coverage=0.90,
            vehicle_bbox_expansion=0.0,
        )[0]

        self.assertIsNone(result.track_id)

    def test_zero_area_bboxes_are_safely_unassociated(self):
        zero_plate = associate_plates_to_vehicles(
            [vehicle(1, (0, 0, 100, 100))], [plate((20, 20, 20, 40))]
        )[0]
        zero_vehicle = associate_plates_to_vehicles(
            [vehicle(2, (10, 10, 10, 100))], [plate((10, 20, 20, 40))]
        )[0]

        self.assertIsNone(zero_plate.track_id)
        self.assertIsNone(zero_vehicle.track_id)

    def test_camera_mismatch_is_not_associated(self):
        result = associate_plates_to_vehicles(
            [vehicle(1, (0, 0, 100, 100), camera_id="cam-02")],
            [plate((30, 40, 70, 60), camera_id="cam-01")],
        )[0]

        self.assertIsNone(result.track_id)

    def test_metadata_is_preserved_and_input_is_not_mutated(self):
        source = plate(
            (30, 40, 70, 60),
            raw_plate_text="mh 12 ab 1234",
            ocr_variant="clahe",
            coordinate_space="frame",
        )
        result = associate_plates_to_vehicles(
            [vehicle(7, (0, 0, 100, 100))], [source]
        )[0]

        self.assertIsNot(result, source)
        self.assertIsNone(source.track_id)
        self.assertIsNone(source.vehicle_bbox)
        self.assertIsNone(source.association_confidence)
        self.assertEqual(result.plate_text, source.plate_text)
        self.assertEqual(result.raw_plate_text, source.raw_plate_text)
        self.assertEqual(result.ocr_variant, source.ocr_variant)
        self.assertEqual(result.detection_confidence, source.detection_confidence)
        self.assertEqual(result.ocr_confidence, source.ocr_confidence)
        self.assertEqual(result.bbox, source.bbox)
        self.assertEqual(result.frame_number, source.frame_number)
        self.assertEqual(result.camera_id, source.camera_id)
        self.assertEqual(result.coordinate_space, source.coordinate_space)

    def test_already_associated_plate_is_preserved(self):
        source = plate(
            (30, 40, 70, 60),
            track_id=99,
            vehicle_bbox=(1, 1, 2, 2),
            association_confidence=0.95,
        )
        result = associate_plates_to_vehicles(
            [vehicle(1, (0, 0, 100, 100))], [source]
        )[0]

        self.assertEqual(result.track_id, 99)
        self.assertEqual(result.vehicle_bbox, (1.0, 1.0, 2.0, 2.0))
        self.assertEqual(result.association_confidence, 0.95)


if __name__ == "__main__":
    unittest.main()
