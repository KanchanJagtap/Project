from fastapi import FastAPI, UploadFile, File, HTTPException
import cv2
import numpy as np

from backend.anpr import process_plate
from backend.real_anpr import get_anpr_pipeline
from backend.vehicle_db import get_vehicle_details


app = FastAPI(
    title="City ANPR Demo API",
    description="AI-powered city traffic intelligence presentation prototype",
    version="1.0.0",
)


@app.get("/")
def home():
    return {
        "status": "running",
        "project": "City ANPR Demo",
        "message": "Backend is working",
    }


@app.get("/health")
def health():
    return {
        "status": "healthy",
    }


@app.get("/anpr-demo")
def anpr_demo():
    return process_plate()


@app.get("/anpr/status")
def anpr_status():
    try:
        pipeline = get_anpr_pipeline()

        return {
            "status": "ready",
            "engine": type(pipeline).__name__,
            "message": "Real ANPR pipeline is loaded",
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e),
        )


@app.post("/anpr/process")
async def process_anpr_image(
    file: UploadFile = File(...)
):
    try:
        contents = await file.read()

        image_array = np.frombuffer(
            contents,
            dtype=np.uint8,
        )

        image = cv2.imdecode(
            image_array,
            cv2.IMREAD_COLOR,
        )

        if image is None:
            raise ValueError(
                "Uploaded file is not a valid image"
            )

        pipeline = get_anpr_pipeline()

        detections = pipeline.detect_and_read(image)

        enriched_detections = []

        for detection in detections:
            plate_number = detection.get("text", "").strip().upper()

            vehicle = None

            if plate_number:
                vehicle = get_vehicle_details(
                    plate_number
                )

            enriched_detections.append(
                {
                    "plate_number": plate_number,
                    "detection_confidence": detection.get(
                        "detection_confidence"
                    ),
                    "ocr_confidence": detection.get(
                        "ocr_confidence"
                    ),
                    "bbox": detection.get("bbox"),
                    "vehicle": vehicle,
                    "vehicle_found": vehicle is not None,
                }
            )

        return {
            "status": "success",
            "filename": file.filename,
            "detection_count": len(enriched_detections),
            "detections": enriched_detections,
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e),
        )