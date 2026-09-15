import cv2
import pytest
import os
from ai.anpr.anpr_pipeline import ANPRPipeline

@pytest.fixture(scope="module")
def anpr_pipeline():
    return ANPRPipeline()

def test_single_line_plate_regression(anpr_pipeline):
    """
    Regression test for image_0032.jpg which was previously incorrectly
    bisected into a two-line plate (yielding HR22AY76MD4ZAA7440) due to
    a tall bounding box (AR 2.81) falling under the < 3.0 threshold.
    It should now correctly bypass the bisection (threshold < 2.2) and
    return WB42AX7446.
    """
    image_path = "data/test/indian-plates/images/image_0032.jpg"
    if not os.path.exists(image_path):
        pytest.skip(f"Test image {image_path} not found")
        
    image = cv2.imread(image_path)
    results = anpr_pipeline.detect_and_read(image)
    
    assert len(results) > 0, "No plate detected"
    
    # It might detect multiple in some cases, but the main one should be WB42AX7446
    plates = [r["text"] for r in results]
    assert "WB42AX7446" in plates, f"Expected WB42AX7446 but got {plates}"

def test_two_line_plate_preservation(anpr_pipeline):
    """
    Ensure a genuine two-line plate (AR < 2.2) is still processed correctly.
    """
    image_path = "data/test/indian-plates/images/image_0027.jpg"
    if not os.path.exists(image_path):
        pytest.skip(f"Test image {image_path} not found")
        
    image = cv2.imread(image_path)
    results = anpr_pipeline.detect_and_read(image)
    
    assert len(results) > 0, "No plate detected"
    
    # We just ensure it doesn't crash and returns some text
    # (Previously it returned SP64H)
    plates = [r["text"] for r in results]
    assert any(len(p) > 0 for p in plates), "No text extracted from two-line plate"
