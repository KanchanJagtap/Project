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

def test_16_real_encoder_smoke():
    import os
    import cv2
    from ai.reid.onnx_encoder import ONNXAppearanceEncoder
    
    # 10.A. Skip gracefully when the model file is absent in CI
    model_path = os.environ.get("REID_MODEL_PATH", "vehicle_vit_clip_reid.onnx")
    if not os.path.exists(model_path):
        pytest.skip(f"Model {model_path} not found. Skipping real inference tests.")
        
    # 10.B. Model loads successfully when present
    encoder = ONNXAppearanceEncoder(model_path)
    
    # Load actual project vehicle crop
    img = cv2.imread('data/test/indian-plates/images/image_0032.jpg')
    if img is None:
        pytest.skip("Test image not found.")
        
    # Fake a bbox that captures the center of the image
    bbox = (278.256, 2.893, 2353.353, 1627.965)
    
    # Extract crop using ai/reid/crop.py to validate the pipeline
    from ai.reid.crop import extract_vehicle_crop
    crop = extract_vehicle_crop(img, bbox)
    
    # 10.C. Input crop is accepted
    emb1 = encoder.encode(crop)
    
    assert emb1 is not None
    # 10.D. Output dimension is exactly 512
    assert emb1.dimension == 512
    # 10.E. Output values are finite, 10.F. Output is non-zero
    assert np.isfinite(emb1.vector).all()
    assert np.any(np.array(emb1.vector) != 0)
    
    # 10.G. L2-normalized output norm is approximately 1
    norm = np.linalg.norm(emb1.vector)
    assert pytest.approx(norm, 0.001) == 1.0
    
    # 10.H. Same crop produces deterministic/near-identical embedding
    emb2 = encoder.encode(crop)
    np.testing.assert_array_almost_equal(emb1.vector, emb2.vector, decimal=5)
    
    # 10.I. Two genuinely different vehicle crops produce different embeddings
    img2 = cv2.imread('data/test/indian-plates/images/image_0026.jpg')
    if img2 is not None:
        bbox2 = (52.137, 406.955, 1968.0, 2953.866)
        crop2 = extract_vehicle_crop(img2, bbox2)
        emb3 = encoder.encode(crop2)
        assert not np.allclose(emb1.vector, emb3.vector, atol=1e-3)
        
        # 10.M. Cosine similarity works with resulting normalized embeddings
        from ai.reid.similarity import cosine_similarity
        sim_diff = cosine_similarity(emb1, emb3)
        assert sim_diff < 1.0
        
        sim_same = cosine_similarity(emb1, emb2)
        assert pytest.approx(sim_same, 0.001) == 1.0
        
    # 10.J. Invalid/too-small crop is rejected cleanly
    invalid_crop = np.zeros((10, 10, 3), dtype=np.uint8)
    assert encoder.encode(invalid_crop) is None

def test_17_reid_service_real_integration():
    import os
    import cv2
    
    model_path = os.environ.get("REID_MODEL_PATH", "vehicle_vit_clip_reid.onnx")
    if not os.path.exists(model_path):
        pytest.skip(f"Model {model_path} not found.")
        
    from ai.reid.service import ReIDService
    service = ReIDService()
    
    # Ensure it didn't fallback to NotImplemented
    from ai.reid.onnx_encoder import ONNXAppearanceEncoder
    assert isinstance(service.encoder, ONNXAppearanceEncoder)
    
    img = cv2.imread('data/test/indian-plates/images/image_0032.jpg')
    if img is None:
        pytest.skip("Test image not found.")
        
    bbox = (278.256, 2.893, 2353.353, 1627.965)
    
    # 10.L. ReIDService successfully returns embedding
    emb = service.extract_evidence(img, bbox)
    assert emb is not None
    assert emb.dimension == 512
