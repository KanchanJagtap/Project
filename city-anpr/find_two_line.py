import cv2
import os
from ai.anpr.anpr_pipeline import ANPRPipeline

pipeline = ANPRPipeline()
folder = "data/test/indian-plates/images/"

for filename in os.listdir(folder):
    if not filename.endswith(".jpg"): continue
    image_path = os.path.join(folder, filename)
    image = cv2.imread(image_path)
    if image is None: continue
    
    results = pipeline.plate_detector(image, verbose=False)
    if not results or not results[0].boxes: continue
    
    box = results[0].boxes[0]
    x1, y1, x2, y2 = map(int, box.xyxy[0])
    w = x2 - x1
    h = y2 - y1
    ar = w / h
    if ar < 2.2:
        print(f"{filename} is two-line! AR: {ar}")
        break
