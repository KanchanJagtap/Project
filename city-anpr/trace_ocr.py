import cv2
import json
from ai.anpr.anpr_pipeline import ANPRPipeline

pipeline = ANPRPipeline()
image_path = "data/test/indian-plates/images/image_0032.jpg"
image = cv2.imread(image_path)

print("Image shape:", image.shape)

# Step 1: Detect
results = pipeline.plate_detector(image, verbose=False)
for r in results:
    for box in r.boxes:
        print("Raw YOLO Box:", box.xyxy[0].cpu().numpy())
        print("Conf:", float(box.conf[0]))
        
        x1, y1, x2, y2 = map(int, box.xyxy[0])
        plate_crop = image[y1:y2, x1:x2]
        print("Crop shape:", plate_crop.shape)
        
        # We need to trace what happens in detect_and_read
        # Let's mock what detect_and_read does.
        # It calls read_plate(plate_crop)
        plate_text, ocr_confidence = pipeline.read_plate(plate_crop)
        print("Final Plate Text:", plate_text)
        print("Final OCR Conf:", ocr_confidence)

