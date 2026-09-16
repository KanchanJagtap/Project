import re

with open('tests/test_reid.py', 'r') as f:
    content = f.read()

# Replace the fake bbox block
content = re.sub(
    r"h, w = img\.shape\[:2\]\n\s*bbox = \(float\(w//4\), float\(h//4\), float\(w\*3//4\), float\(h\*3//4\)\)",
    r"bbox = (278.256, 2.893, 2353.353, 1627.965)",
    content
)

content = re.sub(
    r"img2 = cv2\.imread\('data/test/indian-plates/images/image_0027\.jpg'\)\n\s*if img2 is not None:\n\s*crop2 = extract_vehicle_crop\(img2, bbox\)",
    r"img2 = cv2.imread('data/test/indian-plates/images/image_0026.jpg')\n    if img2 is not None:\n        bbox2 = (52.137, 406.955, 1968.0, 2953.866)\n        crop2 = extract_vehicle_crop(img2, bbox2)",
    content
)

with open('tests/test_reid.py', 'w') as f:
    f.write(content)
