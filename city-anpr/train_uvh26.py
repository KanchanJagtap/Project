from ultralytics import YOLO


# Existing trained model
model = YOLO(
    "runs/detect/runs/cctv/uvh26_test-2/weights/best.pt"
)


# Continue training
model.train(
    data="data/cctv/uvh26_yolo/data.yaml",

    # 40 total epochs for this experiment
    epochs=40,

    imgsz=640,
    batch=4,

    device="mps",
    workers=2,

    project="runs/cctv",
    name="uvh26_40ep",

    # Save checkpoints
    save=True,

    # Validate during training
    val=True,

    # Early stopping if validation stops improving
    patience=10,
)