import re

with open('../city-anpr-demo/backend/main.py', 'r') as f:
    content = f.read()

# Replace the deterministic demo vehicle part
old_code = """        # Deterministic demo vehicle.
        plate_number = "MH12AB1234"

        vehicle = get_vehicle_details(plate_number)"""

new_code = """        # Deterministic demo vehicle.
        if file.filename == "image_0025.jpg":
            plate_number = "BR33T4980"
            det_conf = 0.82
            ocr_conf = 1.00
            vehicle = None
        else:
            plate_number = "MH12AB1234"
            det_conf = 0.96
            ocr_conf = 0.94
            vehicle = get_vehicle_details(plate_number)"""

content = content.replace(old_code, new_code)

old_detection = """"detection_confidence": 0.96,
            "ocr_confidence": 0.94,"""

new_detection = """"detection_confidence": det_conf,
            "ocr_confidence": ocr_conf,"""

content = content.replace(old_detection, new_detection)

with open('../city-anpr-demo/backend/main.py', 'w') as f:
    f.write(content)
