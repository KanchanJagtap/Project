from typing import Optional
import numpy as np
import logging
import os

from ai.contracts.models import AppearanceEmbedding, BoundingBox
from ai.reid.crop import extract_vehicle_crop
from ai.reid.encoder import AppearanceEncoder, NotImplementedReIDEncoder

logger = logging.getLogger(__name__)

class ReIDService:
    """
    Dedicated component for extracting visual Re-ID appearance evidence.
    Kept separate from SingleCameraPipeline to avoid excessive coupling
    and strictly enforce the "Re-ID is evidence, not identity" rule.
    """
    def __init__(self, encoder: Optional[AppearanceEncoder] = None):
        if encoder is None:
            # Default model path (configurable via ENV or passed explicitly if preferred)
            model_path = os.environ.get("REID_MODEL_PATH", "vehicle_vit_clip_reid.onnx")
            if os.path.exists(model_path):
                try:
                    from ai.reid.onnx_encoder import ONNXAppearanceEncoder
                    self.encoder = ONNXAppearanceEncoder(model_path=model_path)
                    logger.info(f"Initialized ReIDService with ONNXAppearanceEncoder ({model_path}).")
                except Exception as e:
                    logger.error(f"Failed to load ONNX encoder, falling back to NotImplemented: {e}")
                    self.encoder = NotImplementedReIDEncoder()
            else:
                logger.info(f"Re-ID model '{model_path}' not found. Defaulting to NotImplemented fallback.")
                self.encoder = NotImplementedReIDEncoder()
        else:
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
            logger.debug(f"Re-ID extraction skipped: {e}")
            return None
        except Exception as e:
            logger.error(f"Re-ID encoder failed during inference: {e}")
            return None
