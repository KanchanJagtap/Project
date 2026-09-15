from typing import Protocol, Optional
import numpy as np
from ai.contracts.models import AppearanceEmbedding

class AppearanceEncoder(Protocol):
    """
    Abstract interface for Visual Re-ID embedding extraction.
    Must generate a deterministic AppearanceEmbedding from a valid vehicle crop.
    """
    
    def encode(self, crop: np.ndarray) -> Optional[AppearanceEmbedding]:
        ...

class NotImplementedReIDEncoder(AppearanceEncoder):
    """
    Explicit fallback encoder indicating that a pretrained model is missing
    from the environment. This strictly blocks the generation of fake embeddings.
    """
    def encode(self, crop: np.ndarray) -> Optional[AppearanceEmbedding]:
        raise NotImplementedError(
            "Pretrained vehicle Re-ID weights (e.g. OSNet on VeRi) are not available in this environment. "
            "A fake embedding is unacceptable per architecture constraints."
        )
