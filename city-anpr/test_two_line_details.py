import cv2
from ai.anpr.anpr_pipeline import ANPRPipeline

pipeline = ANPRPipeline()
image_path = "data/test/indian-plates/images/image_0027.jpg"
image = cv2.imread(image_path)
results = pipeline.detect_and_read(image)
for plate in results:
    print("Text:", plate["text"])
    print("Det Conf:", plate["detection_confidence"])
    print("OCR Conf:", plate["ocr_confidence"])
