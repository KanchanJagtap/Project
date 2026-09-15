import numpy as np
from typing import Optional
from ai.contracts.models import BoundingBox

def extract_vehicle_crop(image: np.ndarray, bbox: BoundingBox, min_width: int = 16, min_height: int = 16) -> Optional[np.ndarray]:
    """
    Extract a clamped, validated vehicle crop from an image.
    Returns None if the clamped bounding box is too small.
    Does not mutate the original image.
    """
    if image is None or image.size == 0:
        return None

    img_h, img_w = image.shape[:2]
    x1, y1, x2, y2 = bbox

    # Clamp to image boundaries
    x1_c = max(0, int(round(x1)))
    y1_c = max(0, int(round(y1)))
    x2_c = min(img_w, int(round(x2)))
    y2_c = min(img_h, int(round(y2)))

    # Reject if empty or invalid
    if x2_c <= x1_c or y2_c <= y1_c:
        return None

    w = x2_c - x1_c
    h = y2_c - y1_c

    # Reject if smaller than minimum quality requirements
    if w < min_width or h < min_height:
        return None

    crop = image[y1_c:y2_c, x1_c:x2_c].copy()
    return crop
