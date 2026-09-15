import os
import cv2
import numpy as np
import logging
from typing import Optional

from ai.contracts.models import AppearanceEmbedding
from ai.reid.encoder import AppearanceEncoder

logger = logging.getLogger(__name__)

class ONNXAppearanceEncoder(AppearanceEncoder):
    """
    Real vehicle Re-ID encoder using an ONNX model.
    Validated with occurra/vehicle_vit_clip_reid (CLIP ViT-B/16 based).
    """
    def __init__(self, model_path: str = "vehicle_vit_clip_reid.onnx"):
        self.model_path = model_path
        self.model_name = os.path.basename(model_path)
        
        if not os.path.exists(self.model_path):
            raise FileNotFoundError(
                f"ONNX Model '{self.model_path}' not found. "
                f"Please download it and place it at the correct path."
            )
            
        import onnxruntime as ort
        providers = ['CoreMLExecutionProvider', 'CPUExecutionProvider']
        
        try:
            self.session = ort.InferenceSession(self.model_path, providers=providers)
            self.input_name = self.session.get_inputs()[0].name
            self.output_name = self.session.get_outputs()[0].name
            self.active_provider = self.session.get_providers()[0]
            logger.info(f"Initialized ONNX encoder with provider: {self.active_provider}")
        except Exception as e:
            raise RuntimeError(f"Failed to initialize ONNX Runtime session: {e}")

    def _preprocess(self, crop: np.ndarray) -> np.ndarray:
        """
        Preprocess the vehicle crop exactly as required by the model.
        - Resize to 256x256
        - BGR to RGB
        - Float32
        - ImageNet Normalization
        - NCHW format
        """
        # Resize
        resized = cv2.resize(crop, (256, 256))
        # BGR -> RGB
        rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
        # Float32, scale to [0,1]
        rgb_float = rgb.astype(np.float32) / 255.0
        
        # ImageNet norm
        mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
        std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
        normalized = (rgb_float - mean) / std
        
        # HWC -> CHW
        chw = normalized.transpose(2, 0, 1)
        
        # Add batch dim (NCHW)
        return np.expand_dims(chw, axis=0)

    def encode(self, crop: np.ndarray) -> Optional[AppearanceEmbedding]:
        if crop is None or crop.size == 0:
            return None
            
        h, w = crop.shape[:2]
        if h < 16 or w < 16:
            logger.warning("Crop is too small for meaningful Re-ID extraction.")
            return None
            
        try:
            # Preprocess
            input_tensor = self._preprocess(crop)
            
            # Inference
            out = self.session.run([self.output_name], {self.input_name: input_tensor})[0]
            
            # Extract raw vector
            raw_vector = out.flatten()
            dimension = len(raw_vector)
            
            if dimension == 0:
                logger.error("ONNX model returned empty vector.")
                return None
                
            if not np.isfinite(raw_vector).all():
                logger.error("ONNX model returned non-finite values.")
                return None
                
            # L2 Normalization (model outputs unnormalized logits/embeddings)
            norm = np.linalg.norm(raw_vector)
            if norm < 1e-12:
                logger.error("ONNX model returned zero-norm vector.")
                return None
                
            normalized_vector = (raw_vector / norm).tolist()
            
            # Quality score proxy based on crop area relative to ideal resolution (256x256)
            quality_score = float(min(1.0, (h * w) / (256.0 * 256.0)))
            
            return AppearanceEmbedding(
                vector=normalized_vector,
                model_name=self.model_name,
                dimension=dimension,
                quality_score=quality_score
            )
            
        except Exception as e:
            logger.error(f"ONNX inference failed: {e}")
            return None
