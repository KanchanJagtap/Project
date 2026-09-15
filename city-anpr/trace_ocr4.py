import cv2
from ai.anpr.anpr_pipeline import ANPRPipeline

pipeline = ANPRPipeline()
image_path = "data/test/indian-plates/images/image_0032.jpg"
image = cv2.imread(image_path)

# Mock recognize_region to run on full image
# wait, predict returns a generator or result object in paddlex
import numpy as np

# Let's just crop to a few parts of the image to see what's there
# Or better, just print all text found by the OCR model on the full image?
# wait, self.ocr is paddlex.TextRecognition which might not do detection, only recognition!
# Let me check if self.ocr does detection.
