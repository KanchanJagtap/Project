from backend.real_anpr import process_image
import json
res = process_image("../data/test/indian-plates/images/image_0025.jpg")
print(json.dumps(res, indent=2))
