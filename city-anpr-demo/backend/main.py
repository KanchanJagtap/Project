from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import cv2
import numpy as np

from backend.anpr import process_plate
from backend.vehicle_db import get_vehicle_details


app = FastAPI(
    title="City ANPR Demo API",
    description="Lightweight AI-powered city traffic intelligence presentation prototype",
    version="2.0.0",
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8443",
        "http://127.0.0.1:8443",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def home():
    return {
        "status": "running",
        "project": "City ANPR Demo",
        "mode": "presentation-demo",
        "message": "Lightweight demo backend is working",
    }


@app.get("/health")
def health():
    return {
        "status": "healthy",
        "mode": "presentation-demo",
    }


@app.get("/anpr-demo")
def anpr_demo():
    return process_plate()


@app.get("/anpr/status")
def anpr_status():
    return {
        "status": "ready",
        "engine": "DemoANPR",
        "message": "Lightweight presentation ANPR engine is ready",
        "mode": "demo",
    }


@app.post("/anpr/process")
async def process_anpr_image(file: UploadFile = File(...)):
    """
    Lightweight presentation-mode ANPR endpoint.

    This intentionally does NOT load YOLO, PaddleOCR, or the
    full city-anpr AI pipeline.

    The endpoint validates the uploaded image and returns a
    deterministic demo detection using the same response
    structure expected by the frontend.
    """

    try:
        contents = await file.read()

        if not contents:
            raise ValueError("Uploaded file is empty")

        image_array = np.frombuffer(contents, dtype=np.uint8)
        image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)

        if image is None:
            raise ValueError("Uploaded file is not a valid image")

        height, width = image.shape[:2]

        # Deterministic demo vehicle.
        plate_number = "MH12AB1234"

        vehicle = get_vehicle_details(plate_number)

        # Generate a plausible center-region bounding box.
        # This is presentation/demo data, not a real detection.
        x1 = int(width * 0.30)
        y1 = int(height * 0.60)
        x2 = int(width * 0.70)
        y2 = int(height * 0.78)

        detection = {
            "plate_number": plate_number,
            "detection_confidence": 0.96,
            "ocr_confidence": 0.94,
            "bbox": [x1, y1, x2, y2],
            "vehicle": vehicle,
            "vehicle_found": vehicle is not None,
            "mode": "demo",
        }

        return {
            "status": "success",
            "filename": file.filename,
            "image_width": width,
            "image_height": height,
            "detection_count": 1,
            "detections": [detection],
            "mode": "presentation-demo",
        }

    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=str(e),
        )
