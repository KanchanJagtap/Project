import json
import shutil
from pathlib import Path
from collections import defaultdict

# ============================================================
# CONFIG
# ============================================================

PROJECT = Path("/Users/rohit/Kanchan Jagtap/SIH Project/city-anpr")

DATASET = PROJECT / "data/cctv/uvh26_10gb"

IMAGE_SOURCE = DATASET / "images"
COCO_JSON = DATASET / "UVH-26-ST-Train.json"

OUTPUT = PROJECT / "data/cctv/uvh26_yolo"

# ============================================================
# LOAD COCO DATA
# ============================================================

print("=" * 70)
print("UVH-26 COCO → YOLO CONVERTER")
print("=" * 70)

print("\nLoading COCO annotations...")

with open(COCO_JSON, "r", encoding="utf-8") as f:
    coco = json.load(f)

images = coco["images"]
annotations = coco["annotations"]
categories = coco["categories"]

print(f"Images       : {len(images):,}")
print(f"Annotations  : {len(annotations):,}")
print(f"Classes      : {len(categories)}")

# ============================================================
# CLASS MAPPING
# ============================================================

# COCO category IDs may not start at zero.
# YOLO requires class IDs starting from 0.

category_to_yolo = {}

for index, category in enumerate(categories):
    category_to_yolo[category["id"]] = index

class_names = [
    category["name"]
    for category in categories
]

print("\nClasses:")

for i, name in enumerate(class_names):
    print(f"  {i}: {name}")

# ============================================================
# IMAGE LOOKUP
# ============================================================

print("\nFinding images...")

local_images = {}

for path in IMAGE_SOURCE.rglob("*.png"):
    local_images[path.name] = path

print(f"Local images found: {len(local_images):,}")

# ============================================================
# ANNOTATION GROUPING
# ============================================================

annotations_by_image = defaultdict(list)

for ann in annotations:
    annotations_by_image[ann["image_id"]].append(ann)

# ============================================================
# CREATE OUTPUT DIRECTORIES
# ============================================================

if OUTPUT.exists():
    print("\nOutput directory already exists.")
    response = input(
        "Delete and recreate it? [y/N]: "
    ).strip().lower()

    if response != "y":
        print("Cancelled.")
        exit()

    shutil.rmtree(OUTPUT)

train_images = OUTPUT / "images" / "train"
train_labels = OUTPUT / "labels" / "train"

val_images = OUTPUT / "images" / "val"
val_labels = OUTPUT / "labels" / "val"

for directory in [
    train_images,
    train_labels,
    val_images,
    val_labels
]:
    directory.mkdir(
        parents=True,
        exist_ok=True
    )

# ============================================================
# TRAIN / VALIDATION SPLIT
# ============================================================

# Your subset was already randomly sampled.
# We now use 80% for training and 20% for validation.

import random

random.seed(42)

shuffled_images = images.copy()
random.shuffle(shuffled_images)

split_index = int(len(shuffled_images) * 0.8)

train_set = shuffled_images[:split_index]
val_set = shuffled_images[split_index:]

print("\nDataset split:")
print(f"Training   : {len(train_set):,}")
print(f"Validation : {len(val_set):,}")

# ============================================================
# CONVERSION FUNCTION
# ============================================================

def convert_split(image_list, image_output, label_output, split_name):

    converted = 0
    missing = 0
    total_boxes = 0

    print(f"\nConverting {split_name}...")

    for i, image_info in enumerate(image_list, 1):

        image_id = image_info["id"]
        filename = Path(image_info["file_name"]).name

        if filename not in local_images:
            missing += 1
            continue

        source_image = local_images[filename]

        # Copy image
        destination_image = image_output / filename

        shutil.copy2(
            source_image,
            destination_image
        )

        # YOLO label filename
        label_file = label_output / (
            Path(filename).stem + ".txt"
        )

        img_width = image_info["width"]
        img_height = image_info["height"]

        lines = []

        for ann in annotations_by_image.get(image_id, []):

            category_id = ann["category_id"]

            if category_id not in category_to_yolo:
                continue

            class_id = category_to_yolo[category_id]

            x, y, w, h = ann["bbox"]

            # COCO:
            # x, y = top-left
            # w, h = width/height

            # YOLO:
            # x_center, y_center, width, height
            # all normalized 0-1

            x_center = (x + w / 2) / img_width
            y_center = (y + h / 2) / img_height

            width = w / img_width
            height = h / img_height

            # Safety clamp
            x_center = max(0, min(1, x_center))
            y_center = max(0, min(1, y_center))
            width = max(0, min(1, width))
            height = max(0, min(1, height))

            lines.append(
                f"{class_id} "
                f"{x_center:.6f} "
                f"{y_center:.6f} "
                f"{width:.6f} "
                f"{height:.6f}"
            )

            total_boxes += 1

        # Write label file
        with open(label_file, "w") as f:
            f.write("\n".join(lines))

        converted += 1

        if i % 100 == 0 or i == len(image_list):
            print(
                f"\r{split_name}: "
                f"{i:,}/{len(image_list):,}",
                end=""
            )

    print()

    print(f"{split_name} converted : {converted:,}")
    print(f"{split_name} missing   : {missing:,}")
    print(f"{split_name} boxes     : {total_boxes:,}")

    return converted, total_boxes, missing


# ============================================================
# CONVERT
# ============================================================

train_count, train_boxes, train_missing = convert_split(
    train_set,
    train_images,
    train_labels,
    "TRAIN"
)

val_count, val_boxes, val_missing = convert_split(
    val_set,
    val_images,
    val_labels,
    "VAL"
)

# ============================================================
# CREATE data.yaml
# ============================================================

yaml_file = OUTPUT / "data.yaml"

with open(yaml_file, "w") as f:

    f.write(
        "path: " + str(OUTPUT) + "\n"
    )

    f.write(
        "train: images/train\n"
    )

    f.write(
        "val: images/val\n\n"
    )

    f.write("names:\n")

    for i, name in enumerate(class_names):
        f.write(
            f"  {i}: {name}\n"
        )

# ============================================================
# FINAL REPORT
# ============================================================

print("\n" + "=" * 70)
print("CONVERSION COMPLETE")
print("=" * 70)

print(f"Training images       : {train_count:,}")
print(f"Training annotations  : {train_boxes:,}")

print(f"Validation images     : {val_count:,}")
print(f"Validation annotations: {val_boxes:,}")

print(f"Missing images        : {train_missing + val_missing}")

print("\nYOLO dataset:")
print(OUTPUT)

print("\nConfiguration:")
print(yaml_file)

print("\nClasses:")

for i, name in enumerate(class_names):
    print(f"  {i}: {name}")

print("=" * 70)
