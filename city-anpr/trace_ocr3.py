import cv2
from ai.anpr.anpr_pipeline import ANPRPipeline

pipeline = ANPRPipeline()
image_path = "data/test/indian-plates/images/image_0032.jpg"
image = cv2.imread(image_path)

results = pipeline.plate_detector(image, verbose=False)
print("Total detections:", len(results[0].boxes))
for idx, box in enumerate(results[0].boxes):
    x1, y1, x2, y2 = map(int, box.xyxy[0])
    conf = float(box.conf[0])
    print(f"Box {idx}: [{x1}, {y1}, {x2}, {y2}] conf: {conf}")
    crop = image[y1:y2, x1:x2]
    plate, conf_ocr = pipeline.read_plate(crop)
    print(f"  Plate: {plate} OCR Conf: {conf_ocr}")

