from ultralytics import YOLO


# ============================================================
# UVH26 VEHICLE DETECTOR - 80 EPOCH FINE-TUNING EXPERIMENT
# ============================================================

# Start from the existing best model.
# This does NOT modify the original checkpoint.
model = YOLO(
    "runs/detect/runs/cctv/uvh26_test-2/weights/best.pt"
)


# Fine-tune the existing model
model.train(
    # Dataset
    data="data/cctv/uvh26_yolo/data.yaml",

    # Training
    epochs=80,
    imgsz=640,
    batch=4,

    # Apple Silicon
    device="mps",
    workers=2,

    # NEW experiment name
    # Keeps the existing uvh26_40ep experiment separate.
    project="runs/cctv",
    name="uvh26_80ep",

    # Checkpoint saving
    save=True,

    # Validation
    val=True,

    # Stop early if validation stops improving
    patience=10,
)