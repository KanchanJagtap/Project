from ultralytics import YOLO
from paddleocr import PaddleOCR
import cv2


# ============================================================
# CONFIGURATION
# ============================================================

VEHICLE_MODEL = "runs/detect/runs/cctv/uvh26_40ep/weights/best.pt"
PLATE_MODEL = "ai/models/license_plate.pt"

SOURCE = "data/videos/traffic.mp4"

VEHICLE_CONF = 0.30
PLATE_CONF = 0.25


# ============================================================
# LOAD MODELS
# ============================================================

print("\n========================================")
print("        CITY ANPR - CCTV PIPELINE")
print("========================================\n")

print("Loading vehicle detector...")
vehicle_model = YOLO(VEHICLE_MODEL)

print("Loading license plate detector...")
plate_model = YOLO(PLATE_MODEL)

print("Loading PaddleOCR...")
ocr = PaddleOCR(
    lang="en",
    use_doc_orientation_classify=False,
    use_doc_unwarping=False,
    use_textline_orientation=False
)

print("\nAll models loaded successfully.\n")


# ============================================================
# OPEN VIDEO
# ============================================================

cap = cv2.VideoCapture(SOURCE)

if not cap.isOpened():
    raise RuntimeError(f"Could not open video: {SOURCE}")

fps = cap.get(cv2.CAP_PROP_FPS)
total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

print(f"Video       : {SOURCE}")
print(f"FPS         : {fps:.2f}")
print(f"Total frames: {total_frames}")
print("\nStarting processing...")
print("Press Q to quit.\n")


frame_number = 0


# ============================================================
# MAIN LOOP
# ============================================================

while True:

    ret, frame = cap.read()

    if not ret:
        break

    frame_number += 1

    # --------------------------------------------------------
    # VEHICLE DETECTION
    # --------------------------------------------------------

    vehicle_results = vehicle_model.predict(
        source=frame,
        imgsz=640,
        conf=VEHICLE_CONF,
        device="mps",
        verbose=False
    )

    for result in vehicle_results:

        if result.boxes is None:
            continue

        for box in result.boxes:

            # Vehicle bounding box
            x1, y1, x2, y2 = map(
                int,
                box.xyxy[0].tolist()
            )

            vehicle_conf = float(box.conf[0])
            class_id = int(box.cls[0])

            vehicle_name = vehicle_model.names[class_id]

            # ------------------------------------------------
            # VEHICLE CROP
            # ------------------------------------------------

            x1 = max(0, x1)
            y1 = max(0, y1)
            x2 = min(frame.shape[1], x2)
            y2 = min(frame.shape[0], y2)

            vehicle_crop = frame[y1:y2, x1:x2]

            if vehicle_crop.size == 0:
                continue

            # ------------------------------------------------
            # LICENSE PLATE DETECTION
            # ------------------------------------------------

            plate_results = plate_model.predict(
                source=vehicle_crop,
                imgsz=640,
                conf=PLATE_CONF,
                device="mps",
                verbose=False
            )

            plate_found = False

            for plate_result in plate_results:

                if plate_result.boxes is None:
                    continue

                for plate_box in plate_result.boxes:

                    plate_found = True

                    # Plate coordinates inside vehicle crop
                    px1, py1, px2, py2 = map(
                        int,
                        plate_box.xyxy[0].tolist()
                    )

                    plate_conf = float(
                        plate_box.conf[0]
                    )

                    # ------------------------------------------------
                    # PLATE CROP
                    # ------------------------------------------------

                    px1 = max(0, px1)
                    py1 = max(0, py1)
                    px2 = min(vehicle_crop.shape[1], px2)
                    py2 = min(vehicle_crop.shape[0], py2)

                    plate_crop = vehicle_crop[
                        py1:py2,
                        px1:px2
                    ]

                    if plate_crop.size == 0:
                        continue

                    # ------------------------------------------------
                    # OCR
                    # ------------------------------------------------

                    plate_text = ""

                    try:

                        ocr_result = ocr.predict(
                            plate_crop
                        )

                        for res in ocr_result:

                            data = res.json

                            if isinstance(data, dict):

                                result_data = data.get(
                                    "res",
                                    {}
                                )

                                texts = result_data.get(
                                    "rec_texts",
                                    []
                                )

                                scores = result_data.get(
                                    "rec_scores",
                                    []
                                )

                                if texts:

                                    valid_texts = []

                                    for i, text in enumerate(texts):

                                        if i < len(scores):

                                            score = float(
                                                scores[i]
                                            )

                                            if score >= 0.20:
                                                valid_texts.append(
                                                    str(text)
                                                )

                                        else:
                                            valid_texts.append(
                                                str(text)
                                            )

                                    plate_text = " ".join(
                                        valid_texts
                                    )

                    except Exception as e:

                        print(
                            f"OCR error on frame "
                            f"{frame_number}: {e}"
                        )

                    # ------------------------------------------------
                    # ABSOLUTE PLATE COORDINATES
                    # ------------------------------------------------

                    ax1 = x1 + px1
                    ay1 = y1 + py1
                    ax2 = x1 + px2
                    ay2 = y1 + py2

                    # ------------------------------------------------
                    # DRAW VEHICLE
                    # ------------------------------------------------

                    cv2.rectangle(
                        frame,
                        (x1, y1),
                        (x2, y2),
                        (0, 255, 0),
                        2
                    )

                    # ------------------------------------------------
                    # DRAW PLATE
                    # ------------------------------------------------

                    cv2.rectangle(
                        frame,
                        (ax1, ay1),
                        (ax2, ay2),
                        (255, 0, 0),
                        2
                    )

                    # ------------------------------------------------
                    # DISPLAY LABEL
                    # ------------------------------------------------

                    if plate_text:

                        label = (
                            f"{vehicle_name} | "
                            f"{plate_text}"
                        )

                    else:

                        label = (
                            f"{vehicle_name} | "
                            f"plate detected"
                        )

                    cv2.putText(
                        frame,
                        label,
                        (x1, max(30, y1 - 10)),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.65,
                        (0, 255, 0),
                        2
                    )

                    # ------------------------------------------------
                    # TERMINAL OUTPUT
                    # ------------------------------------------------

                    print(
                        f"Frame {frame_number:5d} | "
                        f"Vehicle: {vehicle_name:<16} "
                        f"({vehicle_conf:.2f}) | "
                        f"Plate: {plate_text or 'NOT READ':<15} | "
                        f"Plate conf: {plate_conf:.2f}"
                    )

            # --------------------------------------------------------
            # VEHICLE WITHOUT PLATE
            # --------------------------------------------------------

            if not plate_found:

                cv2.rectangle(
                    frame,
                    (x1, y1),
                    (x2, y2),
                    (0, 255, 0),
                    2
                )

                label = (
                    f"{vehicle_name} "
                    f"{vehicle_conf:.2f}"
                )

                cv2.putText(
                    frame,
                    label,
                    (x1, max(30, y1 - 10)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.65,
                    (0, 255, 0),
                    2
                )

    # ========================================================
    # FRAME INFORMATION
    # ========================================================

    info = (
        f"Frame: {frame_number}/{total_frames}"
    )

    cv2.putText(
        frame,
        info,
        (20, 35),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (255, 255, 255),
        2
    )

    # ========================================================
    # DISPLAY
    # ========================================================

    cv2.imshow(
        "CITY ANPR - CCTV",
        frame
    )

    key = cv2.waitKey(1) & 0xFF

    if key == ord("q"):
        break


# ============================================================
# CLEANUP
# ============================================================

cap.release()
cv2.destroyAllWindows()

print("\n========================================")
print("       CCTV PROCESSING COMPLETE")
print("========================================")