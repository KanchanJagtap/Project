from pathlib import Path
import sys

import cv2


# ------------------------------------------------------------
# Locate the original city-anpr project
# ------------------------------------------------------------

PROJECT_ROOT = (
    Path(__file__).resolve().parents[2]
    / "city-anpr"
)

ANPR_DIRECTORY = PROJECT_ROOT / "ai"

PLATE_MODEL = (
    PROJECT_ROOT
    / "ai"
    / "models"
    / "license_plate.pt"
)


# ------------------------------------------------------------
# Make the original AI package importable
# ------------------------------------------------------------

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from ai.anpr.anpr_pipeline import ANPRPipeline


# ------------------------------------------------------------
# Create the real ANPR engine
# ------------------------------------------------------------

_anpr_pipeline = None


def get_anpr_pipeline():
    global _anpr_pipeline

    if _anpr_pipeline is None:

        if not PLATE_MODEL.exists():
            raise FileNotFoundError(
                f"License plate model not found: {PLATE_MODEL}"
            )

        _anpr_pipeline = ANPRPipeline(
            plate_model_path=str(PLATE_MODEL)
        )

    return _anpr_pipeline


# ------------------------------------------------------------
# Process an image using the real ANPR pipeline
# ------------------------------------------------------------

def process_image(image_path: str):

    image = cv2.imread(image_path)

    if image is None:
        raise ValueError(
            f"Unable to read image: {image_path}"
        )

    pipeline = get_anpr_pipeline()

    detections = pipeline.detect_and_read(image)

    return {
        "image": Path(image_path).name,
        "detections": detections,
        "detection_count": len(detections),
    }