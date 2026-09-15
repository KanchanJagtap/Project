import cv2
from ai.anpr.anpr_pipeline import ANPRPipeline

pipeline = ANPRPipeline()
image_path = "data/test/indian-plates/images/image_0032.jpg"
image = cv2.imread(image_path)

# Mock detect
results = pipeline.plate_detector(image, verbose=False)
box = results[0].boxes[0]
x1, y1, x2, y2 = map(int, box.xyxy[0])
plate_crop = image[y1:y2, x1:x2]

# manual read_plate logic
rectified = pipeline.rectify_plate(plate_crop)
h, w = rectified.shape[:2]
aspect_ratio = w / h
print("Rectified shape:", rectified.shape)
print("Aspect Ratio:", aspect_ratio)

is_two_line = aspect_ratio < 3.0
print("Is Two Line:", is_two_line)

margin_y = int(h * 0.05)
usable = rectified[margin_y:h - margin_y, :]
usable_h = usable.shape[0]
split = int(usable_h * 0.50)

top_line = usable[:split, :]
bottom_line = usable[split:, :]

print("Top line shape:", top_line.shape)
print("Bottom line shape:", bottom_line.shape)

top_text, top_score = pipeline.recognize_region(top_line)
print("Top Text RAW (from recognize_region):", top_text, "Conf:", top_score)

bot_text, bot_score = pipeline.recognize_region(bottom_line)
print("Bot Text RAW (from recognize_region):", bot_text, "Conf:", bot_score)

full_text = top_text + bot_text
print("Full combined:", full_text)

cleaned = pipeline.clean_plate_text(full_text)
print("Cleaned:", cleaned)
