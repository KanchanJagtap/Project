import json
import random
import shutil
from pathlib import Path
from collections import defaultdict

# ============================================================
# CONFIG
# ============================================================

PROJECT = Path("/Users/rohit/Kanchan Jagtap/SIH Project/city-anpr")

SOURCE_ROOT = PROJECT / "data/cctv/uvh26/UVH-26-Train"
IMAGE_ROOT = SOURCE_ROOT / "data"
ANNOTATION_FILE = SOURCE_ROOT / "UVH-26-ST-Train.json"

OUTPUT_ROOT = PROJECT / "data/cctv/uvh26_10gb"
OUTPUT_IMAGE_ROOT = OUTPUT_ROOT / "images"
OUTPUT_JSON = OUTPUT_ROOT / "UVH-26-ST-Train.json"

TARGET_IMAGES = 3000
RANDOM_SEED = 42

# ============================================================
# LOAD ANNOTATIONS
# ============================================================

print("=" * 70)
print("UVH-26 SAFE SUBSET CREATOR")
print("=" * 70)

print("\nLoading annotation file...")
with open(ANNOTATION_FILE, "r", encoding="utf-8") as f:
    coco = json.load(f)

images = coco["images"]
annotations = coco["annotations"]
categories = coco["categories"]

print(f"Images in JSON       : {len(images):,}")
print(f"Annotations           : {len(annotations):,}")
print(f"Categories            : {len(categories)}")

# ============================================================
# FIND LOCAL IMAGES
# ============================================================

print("\nFinding local PNG files...")

local_files = list(IMAGE_ROOT.rglob("*.png"))

print(f"Local PNG files found : {len(local_files):,}")

# Map filename -> actual path
file_map = {}

for path in local_files:
    file_map[path.name] = path

# ============================================================
# MATCH JSON IMAGES TO LOCAL FILES
# ============================================================

matched = []
missing = []

for img in images:
    filename = Path(img["file_name"]).name

    if filename in file_map:
        matched.append((img, file_map[filename]))
    else:
        missing.append(img["file_name"])

print(f"Matched images        : {len(matched):,}")
print(f"Missing images        : {len(missing):,}")

if len(matched) < TARGET_IMAGES:
    raise RuntimeError(
        f"Only {len(matched)} images are available, "
        f"but {TARGET_IMAGES} were requested."
    )

# ============================================================
# GROUP IMAGES BY SOURCE FOLDER
# ============================================================

groups = defaultdict(list)

for img, path in matched:
    # Example: data/000/270196.png
    relative = path.relative_to(IMAGE_ROOT)

    if len(relative.parts) >= 2:
        folder = relative.parts[0]
    else:
        folder = "unknown"

    groups[folder].append((img, path))

print("\nSource folders:")

for folder in sorted(groups):
    print(f"  {folder}: {len(groups[folder]):,}")

# ============================================================
# STRATIFIED RANDOM SAMPLING
# ============================================================

random.seed(RANDOM_SEED)

total_available = len(matched)

selected = []

# Allocate approximately proportional number of images
for folder in sorted(groups):

    group = groups[folder]

    quota = round(
        TARGET_IMAGES * len(group) / total_available
    )

    quota = min(quota, len(group))

    chosen = random.sample(group, quota)

    selected.extend(chosen)

# Fix rounding difference
if len(selected) < TARGET_IMAGES:

    selected_set = {img["id"] for img, path in selected}

    remaining = [
        item
        for item in matched
        if item[0]["id"] not in selected_set
    ]

    extra = random.sample(
        remaining,
        TARGET_IMAGES - len(selected)
    )

    selected.extend(extra)

elif len(selected) > TARGET_IMAGES:

    selected = random.sample(
        selected,
        TARGET_IMAGES
    )

print("\nSelected images       :", len(selected))

# ============================================================
# CREATE OUTPUT DIRECTORY
# ============================================================

if OUTPUT_ROOT.exists():
    print("\nOutput directory already exists.")

    response = input(
        "Delete existing subset and recreate it? [y/N]: "
    ).strip().lower()

    if response != "y":
        print("Cancelled.")
        exit()

    shutil.rmtree(OUTPUT_ROOT)

OUTPUT_IMAGE_ROOT.mkdir(
    parents=True,
    exist_ok=True
)

# ============================================================
# COPY IMAGES
# ============================================================

print("\nCopying images...")

selected_image_ids = set()

total_bytes = 0

for index, (img, source_path) in enumerate(selected, start=1):

    selected_image_ids.add(img["id"])

    relative = source_path.relative_to(IMAGE_ROOT)

    destination = OUTPUT_IMAGE_ROOT / relative

    destination.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    shutil.copy2(source_path, destination)

    total_bytes += source_path.stat().st_size

    if index % 100 == 0 or index == len(selected):
        size_gb = total_bytes / (1024 ** 3)

        print(
            f"\rCopied {index:,}/{len(selected):,} "
            f"| {size_gb:.2f} GB",
            end=""
        )

print()

# ============================================================
# FILTER ANNOTATIONS
# ============================================================

print("\nFiltering annotations...")

selected_images = [
    img
    for img in images
    if img["id"] in selected_image_ids
]

selected_annotations = [
    ann
    for ann in annotations
    if ann["image_id"] in selected_image_ids
]

subset_coco = {
    "info": coco.get("info", {}),
    "licenses": coco.get("licenses", []),
    "images": selected_images,
    "annotations": selected_annotations,
    "categories": categories,
}

# ============================================================
# SAVE NEW JSON
# ============================================================

print("Writing annotation JSON...")

with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
    json.dump(
        subset_coco,
        f,
        indent=2
    )

# ============================================================
# VERIFY
# ============================================================

print("\nVerifying subset...")

missing_output = []

for img in selected_images:

    filename = Path(img["file_name"]).name

    # Search based on filename
    matches = list(
        OUTPUT_IMAGE_ROOT.rglob(filename)
    )

    if not matches:
        missing_output.append(img["file_name"])

if missing_output:
    print(
        f"ERROR: {len(missing_output)} images are missing!"
    )
    print(missing_output[:10])
    raise RuntimeError("Subset verification failed.")

# Check annotation references
image_ids = {
    img["id"]
    for img in selected_images
}

bad_annotations = [
    ann
    for ann in selected_annotations
    if ann["image_id"] not in image_ids
]

if bad_annotations:
    raise RuntimeError(
        "Some annotations reference images "
        "that are not in the subset."
    )

# ============================================================
# FINAL REPORT
# ============================================================

json_size = OUTPUT_JSON.stat().st_size

print("\n" + "=" * 70)
print("SUBSET CREATED SUCCESSFULLY")
print("=" * 70)

print(f"Images              : {len(selected_images):,}")
print(f"Annotations          : {len(selected_annotations):,}")
print(f"Image data           : {total_bytes / (1024 ** 3):.2f} GB")
print(f"Annotation JSON      : {json_size / (1024 ** 2):.2f} MB")
print(
    f"Approx total         : "
    f"{(total_bytes + json_size) / (1024 ** 3):.2f} GB"
)

print("\nOutput:")
print(OUTPUT_ROOT)

print("\nVerification:")
print("✓ All selected images exist")
print("✓ All annotations reference selected images")
print("✓ Original dataset was not modified")

print("=" * 70)
