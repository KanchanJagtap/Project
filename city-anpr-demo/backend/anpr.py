from backend.vehicle_db import get_vehicle_details


def process_plate():
    """
    Temporary presentation-demo ANPR result.

    This will later be replaced with the real ANPR pipeline
    from the main city-anpr project.
    """

    detected_plate = "MH12AB1234"

    vehicle = get_vehicle_details(detected_plate)

    return {
        "plate_number": detected_plate,
        "plate_detection_confidence": 0.96,
        "ocr_confidence": 0.94,
        "vehicle": vehicle,
        "traffic": {
            "lane": "L1",
            "movement": "Moving",
            "signal_priority": "Normal",
        },
    }