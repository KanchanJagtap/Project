"""
Tests for 3A.2 Re-ID Evidence Extraction Foundation.
"""
import pytest
import numpy as np
from ai.contracts.models import AppearanceEmbedding
from ai.reid.crop import extract_vehicle_crop
from ai.reid.encoder import AppearanceEncoder, NotImplementedReIDEncoder
from ai.reid.similarity import cosine_similarity
from ai.reid.service import ReIDService

def test_1_valid_bbox_crop():
    img = np.zeros((100, 100, 3), dtype=np.uint8)
    crop = extract_vehicle_crop(img, (10.0, 10.0, 50.0, 50.0))
    assert crop is not None
    assert crop.shape == (40, 40, 3)

def test_2_bbox_clamping():
    img = np.zeros((100, 100, 3), dtype=np.uint8)
    # Outside bounds
    crop = extract_vehicle_crop(img, (-10.0, -10.0, 150.0, 150.0))
    assert crop is not None
    assert crop.shape == (100, 100, 3)

def test_3_invalid_empty_bbox():
    img = np.zeros((100, 100, 3), dtype=np.uint8)
    crop1 = extract_vehicle_crop(img, (50.0, 50.0, 50.0, 50.0)) # Empty
    crop2 = extract_vehicle_crop(img, (60.0, 60.0, 50.0, 50.0)) # Invalid coords
    assert crop1 is None
    assert crop2 is None

def test_4_crop_does_not_mutate():
    img = np.ones((100, 100, 3), dtype=np.uint8)
    crop = extract_vehicle_crop(img, (10.0, 10.0, 50.0, 50.0))
    # Modify crop
    crop.fill(0)
    # Source image should still be 1s
    assert img[20, 20, 0] == 1

def test_5_deterministic_preprocessing():
    img = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
    crop1 = extract_vehicle_crop(img, (10.0, 10.0, 50.0, 50.0))
    crop2 = extract_vehicle_crop(img, (10.0, 10.0, 50.0, 50.0))
    np.testing.assert_array_equal(crop1, crop2)

def test_6_7_8_embedding_contract_and_dimension():
    # Dimension matches vector length
    emb = AppearanceEmbedding(
        vector=[0.1, 0.2, 0.3],
        model_name="test_model",
        dimension=3,
        quality_score=0.9
    )
    assert emb.dimension == 3
    assert emb.model_name == "test_model"

    with pytest.raises(ValueError, match="vector length"):
        AppearanceEmbedding(vector=[0.1, 0.2], model_name="test_model", dimension=3)

def test_9_encoder_interface():
    # Using the explicit Not Implemented fallback
    encoder = NotImplementedReIDEncoder()
    crop = np.zeros((40, 40, 3), dtype=np.uint8)
    with pytest.raises(NotImplementedError, match="Pretrained vehicle Re-ID weights"):
        encoder.encode(crop)

def test_10_11_cosine_similarity():
    emb1 = AppearanceEmbedding([1.0, 0.0], "model_A", 2)
    emb2 = AppearanceEmbedding([1.0, 0.0], "model_A", 2) # Identical
    assert pytest.approx(cosine_similarity(emb1, emb2)) == 1.0

def test_12_orthogonal_similarity():
    emb1 = AppearanceEmbedding([1.0, 0.0], "model_A", 2)
    emb2 = AppearanceEmbedding([0.0, 1.0], "model_A", 2) # Orthogonal
    assert pytest.approx(cosine_similarity(emb1, emb2)) == 0.0

def test_13_invalid_dimension_similarity():
    emb1 = AppearanceEmbedding([1.0, 0.0], "model_A", 2)
    emb2 = AppearanceEmbedding([1.0, 0.0, 0.5], "model_A", 3)
    with pytest.raises(ValueError, match="Embedding dimensions mismatch"):
        cosine_similarity(emb1, emb2)

    emb3 = AppearanceEmbedding([1.0, 0.0], "model_B", 2)
    with pytest.raises(ValueError, match="different models"):
        cosine_similarity(emb1, emb3)

def test_14_missing_crop_handling():
    # If crop is too small, service returns None
    service = ReIDService(NotImplementedReIDEncoder())
    img = np.zeros((100, 100, 3), dtype=np.uint8)
    # 2x2 crop is rejected
    result = service.extract_evidence(img, (10, 10, 12, 12))
    assert result is None

def test_15_graceful_model_failure():
    service = ReIDService(NotImplementedReIDEncoder())
    img = np.zeros((100, 100, 3), dtype=np.uint8)
    result = service.extract_evidence(img, (10.0, 10.0, 50.0, 50.0))
    # Encoder raises NotImplementedError, service catches it and returns None
    assert result is None
