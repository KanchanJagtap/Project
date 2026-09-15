import re

with open('backend/app/api/endpoints/processing.py', 'r') as f:
    content = f.read()

# Add imports if missing
if 'from fastapi import' in content and 'UploadFile' not in content:
    content = content.replace('from fastapi import APIRouter, Depends, HTTPException, Query, status', 'from fastapi import APIRouter, Depends, HTTPException, Query, status, UploadFile, File')

new_endpoint = """
import cv2
import numpy as np

@router.post(
    "/anpr_scan",
    status_code=status.HTTP_200_OK,
    summary="Real ANPR Image Scan",
    description="Process an uploaded image using the actual ANPR pipeline.",
)
async def process_anpr_image(file: UploadFile = File(...)):
    try:
        contents = await file.read()
        if not contents:
            raise ValueError("Uploaded file is empty")

        image_array = np.frombuffer(contents, dtype=np.uint8)
        image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)

        if image is None:
            raise ValueError("Uploaded file is not a valid image")

        height, width = image.shape[:2]

        from ai.anpr.anpr_pipeline import ANPRPipeline
        pipeline = ANPRPipeline()
        result = pipeline.process_frame(image)

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

        return {
            "status": "success",
            "filename": file.filename,
            "image_width": width,
            "image_height": height,
            "detection_count": 1,
            "detections": [detection],
            "mode": "real",
        }

    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=str(e),
        )
"""

content = content + "\n" + new_endpoint

with open('backend/app/api/endpoints/processing.py', 'w') as f:
    f.write(content)
