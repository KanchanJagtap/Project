with open('backend/app/api/endpoints/processing.py', 'r') as f:
    content = f.read()

content = content.replace("result = pipeline.process_frame(image)", "results = pipeline.detect_and_read(image)")

new_block = """
        if not results:
            return {
                "status": "success",
                "filename": file.filename,
                "image_width": width,
                "image_height": height,
                "detection_count": 0,
                "detections": [],
                "mode": "real"
            }

        result = results[0]
        x1, y1, x2, y2 = result["bbox"]
        detection = {
            "plate_number": result["text"],
            "detection_confidence": result["detection_confidence"],
            "ocr_confidence": result["ocr_confidence"],
            "bbox": [int(x1), int(y1), int(x2), int(y2)],
            "vehicle": None,
            "vehicle_found": False,
            "mode": "real",
        }
"""

old_block = """
        if not result or not result.license_plate_text:
            return {
                "status": "success",
                "filename": file.filename,
                "image_width": width,
                "image_height": height,
                "detection_count": 0,
                "detections": [],
                "mode": "real"
            }

        x1, y1, x2, y2 = result.bounding_box
        detection = {
            "plate_number": result.license_plate_text,
            "detection_confidence": result.detection_confidence,
            "ocr_confidence": result.ocr_confidence,
            "bbox": [int(x1), int(y1), int(x2), int(y2)],
            "vehicle": None,
            "vehicle_found": False,
            "mode": "real",
        }
"""

content = content.replace(old_block.strip(), new_block.strip())

with open('backend/app/api/endpoints/processing.py', 'w') as f:
    f.write(content)
