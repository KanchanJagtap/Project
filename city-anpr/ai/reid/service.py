from typing import Optional, List
import numpy as np
import logging

from ai.contracts.models import AppearanceEmbedding, BoundingBox
from ai.reid.crop import extract_vehicle_crop
from ai.reid.encoder import AppearanceEncoder

logger = logging.getLogger(__name__)

class ReIDService:
    """
    Dedicated component for extracting visual Re-ID appearance evidence.
    Kept separate from SingleCameraPipeline to avoid excessive coupling
    and strictly enforce the "Re-ID is evidence, not identity" rule.
    """
    def __init__(self, encoder: Optional[AppearanceEncoder] = None):
        self.encoder = encoder

    def extract_evidence(
        self, 
        image: np.ndarray, 
        bbox: BoundingBox
    ) -> Optional[AppearanceEmbedding]:
        """
        Takes an image and a bounding box, extracts a valid crop,
        and generates an appearance embedding. Returns None if 
        extraction fails (e.g. invalid bbox or missing model).
        """
        if self.encoder is None:
            return None

        # 1. Appearance Crop Extraction
        crop = extract_vehicle_crop(image, bbox)
        if crop is None:
            logger.debug("Crop extraction failed: invalid or too small bbox.")
            return None

        # 2. Re-ID Encoder Abstraction
        try:
            embedding = self.encoder.encode(crop)
            return embedding
        except NotImplementedError as e:
            logger.warning(f"Re-ID extraction skipped: {e}")
            return None
        except Exception as e:
            logger.error(f"Re-ID encoder failed during inference: {e}")
            return None
