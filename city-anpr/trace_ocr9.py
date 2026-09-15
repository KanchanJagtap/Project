import cv2
from ai.anpr.anpr_pipeline import ANPRPipeline

pipeline = ANPRPipeline()
image_path = "data/test/indian-plates/images/image_0032.jpg"
image = cv2.imread(image_path)

results = pipeline.plate_detector(image, verbose=False)
box = results[0].boxes[0]
x1, y1, x2, y2 = map(int, box.xyxy[0])
plate_crop = image[y1:y2, x1:x2]

info = pipeline.find_plate_corners(plate_crop)
print("Corners:", info)

