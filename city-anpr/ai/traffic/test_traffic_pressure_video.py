"""
Traffic Pressure Engine V3 - CCTV Integration

Uses:
- YOLO vehicle detection
- ByteTrack persistent tracking
- TrafficPressureEngine V3
- Persistent vehicle history
- Queue detection
- Waiting time
- Rolling arrival rate
- Traffic pressure smoothing

Prototype only.
"""

import cv2
from ultralytics import YOLO

from ai.traffic.traffic_pressure import TrafficPressureEngine


# ============================================================
# CONFIGURATION
# ============================================================

VIDEO_PATH = "data/videos/traffic.mp4"

MODEL_PATH = "yolo11n.pt"

VEHICLE_CLASSES = {
    2: "car",
    3: "motorcycle",
    5: "bus",
    7: "truck",
}

PRINT_EVERY = 30


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("=" * 70)
    print("TRAFFIC PRESSURE V3 - PERSISTENT CCTV TRACKING")
    print("=" * 70)

    # --------------------------------------------------------
    # Open video
    # --------------------------------------------------------

    cap = cv2.VideoCapture(VIDEO_PATH)

    if not cap.isOpened():

        print()
        print("ERROR: Could not open video:")
        print(VIDEO_PATH)
        return

    # --------------------------------------------------------
    # Video metadata
    # --------------------------------------------------------

    frame_width = int(
        cap.get(cv2.CAP_PROP_FRAME_WIDTH)
    )

    frame_height = int(
        cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
    )

    fps = cap.get(
        cv2.CAP_PROP_FPS
    )

    total_frames = int(
        cap.get(cv2.CAP_PROP_FRAME_COUNT)
    )

    if fps <= 0:
        fps = 30.0

    duration = (
        total_frames / fps
    )

    print()
    print("Video Information")
    print("-" * 70)

    print(
        f"Video              : {VIDEO_PATH}"
    )

    print(
        f"Resolution         : "
        f"{frame_width} x {frame_height}"
    )

    print(
        f"FPS                : {fps:.2f}"
    )

    print(
        f"Total Frames       : {total_frames}"
    )

    print(
        f"Duration           : {duration:.2f} seconds"
    )

    # --------------------------------------------------------
    # Load YOLO
    # --------------------------------------------------------

    print()
    print("Loading YOLO model...")

    model = YOLO(
        MODEL_PATH
    )

    print("YOLO model loaded.")

    # --------------------------------------------------------
    # Traffic Pressure Engine V3
    # --------------------------------------------------------

    engine = TrafficPressureEngine()

    print(
        "Traffic Pressure Engine V3 loaded."
    )

    # --------------------------------------------------------
    # Persistent vehicle history
    # --------------------------------------------------------

    vehicle_history = {}

    # --------------------------------------------------------
    # Statistics
    # --------------------------------------------------------

    frame_number = 0

    frames_with_vehicles = 0

    frames_without_vehicles = 0

    pressure_values = []

    traffic_levels = {
        "LOW": 0,
        "MEDIUM": 0,
        "HIGH": 0,
        "CRITICAL": 0,
    }

    peak_pressure = -1

    peak_frame = 0

    peak_time = 0.0

    # --------------------------------------------------------
    # Unique vehicle type IDs
    # --------------------------------------------------------

    unique_vehicle_ids = set()

    # --------------------------------------------------------
    # Start ByteTrack
    # --------------------------------------------------------

    print()
    print("Starting ByteTrack...")
    print()

    results = model.track(
        source=VIDEO_PATH,
        tracker="bytetrack.yaml",
        classes=list(
            VEHICLE_CLASSES.keys()
        ),
        persist=True,
        stream=True,
        verbose=False,
    )

    # ========================================================
    # FRAME LOOP
    # ========================================================

    for result in results:

        frame_number += 1

        active_vehicles = []

        # ----------------------------------------------------
        # Process detections
        # ----------------------------------------------------

        if result.boxes is not None:

            boxes = result.boxes

            for box in boxes:

                # --------------------------------------------
                # Track ID
                # --------------------------------------------

                if box.id is None:
                    continue

                track_id = int(
                    box.id[0]
                )

                # --------------------------------------------
                # Class
                # --------------------------------------------

                class_id = int(
                    box.cls[0]
                )

                if class_id not in VEHICLE_CLASSES:
                    continue

                vehicle_type = (
                    VEHICLE_CLASSES[
                        class_id
                    ]
                )

                # --------------------------------------------
                # Confidence
                # --------------------------------------------

                confidence = float(
                    box.conf[0]
                )

                # --------------------------------------------
                # Bounding box
                # --------------------------------------------

                x1, y1, x2, y2 = map(
                    int,
                    box.xyxy[0].tolist()
                )

                # --------------------------------------------
                # Vehicle record
                # --------------------------------------------

                vehicle = {

                    "id": track_id,

                    "type": vehicle_type,

                    "confidence": confidence,

                    "bbox": [
                        x1,
                        y1,
                        x2,
                        y2,
                    ],
                }

                active_vehicles.append(
                    vehicle
                )

                unique_vehicle_ids.add(
                    track_id
                )

        # ----------------------------------------------------
        # Frame statistics
        # ----------------------------------------------------

        if active_vehicles:

            frames_with_vehicles += 1

        else:

            frames_without_vehicles += 1

        # ----------------------------------------------------
        # Calculate Traffic Pressure V3
        # ----------------------------------------------------

        result_data = (
            engine.calculate_pressure(

                active_vehicles=(
                    active_vehicles
                ),

                vehicle_history=(
                    vehicle_history
                ),

                current_frame=(
                    frame_number
                ),

                fps=fps,

                frame_width=(
                    frame_width
                ),

                frame_height=(
                    frame_height
                ),
            )
        )

        # ----------------------------------------------------
        # Pressure
        # ----------------------------------------------------

        pressure = result_data[
            "pressure"
        ]

        traffic_level = result_data[
            "traffic_level"
        ]

        pressure_values.append(
            pressure
        )

        traffic_levels[
            traffic_level
        ] += 1

        # ----------------------------------------------------
        # Peak pressure
        # ----------------------------------------------------

        if pressure > peak_pressure:

            peak_pressure = pressure

            peak_frame = frame_number

            peak_time = (
                frame_number /
                fps
            )

        # ----------------------------------------------------
        # Progress
        # ----------------------------------------------------

        if (
            frame_number == 1
            or
            frame_number % PRINT_EVERY == 0
            or
            frame_number == total_frames
        ):

            print(
                f"Frame {frame_number:<4} | "
                f"Time {frame_number / fps:>5.2f}s | "
                f"Active "
                f"{result_data['active_vehicle_count']:<3} | "
                f"Unique "
                f"{result_data['unique_vehicle_count']:<3} | "
                f"Queue "
                f"{result_data['queue_length']:<2} | "
                f"Moving "
                f"{result_data['moving_vehicles']:<2} | "
                f"Slow "
                f"{result_data['slow_vehicles']:<2} | "
                f"Stationary "
                f"{result_data['stationary_vehicles']:<2} | "
                f"Pressure "
                f"{pressure:>6.2f} | "
                f"{traffic_level}"
            )

    # ========================================================
    # RELEASE VIDEO
    # ========================================================

    cap.release()

    # ========================================================
    # FINAL REPORT
    # ========================================================

    print()
    print("=" * 70)
    print("FINAL CCTV TRAFFIC PRESSURE V3 REPORT")
    print("=" * 70)

    print()

    print("Video Information")
    print("-" * 70)

    print(
        f"Resolution         : "
        f"{frame_width} x {frame_height}"
    )

    print(
        f"FPS                : "
        f"{fps:.2f}"
    )

    print(
        f"Total Frames       : "
        f"{total_frames}"
    )

    print(
        f"Duration           : "
        f"{duration:.2f} seconds"
    )

    print()

    print("Processing")
    print("-" * 70)

    print(
        f"Frames Processed   : "
        f"{frame_number}"
    )

    print(
        f"Frames With Vehicles : "
        f"{frames_with_vehicles}"
    )

    print(
        f"Frames Without Vehicles : "
        f"{frames_without_vehicles}"
    )

    print(
        f"Unique Tracked Vehicles : "
        f"{len(unique_vehicle_ids)}"
    )

    print()

    # ========================================================
    # VEHICLE TYPES
    # ========================================================

    print("UNIQUE VEHICLE TYPES")
    print("-" * 70)

    final_type_counts = {}

    for vehicle in vehicle_history.values():

        vehicle_type = vehicle.get(
            "type",
            "unknown"
        )

        final_type_counts[
            vehicle_type
        ] = (
            final_type_counts.get(
                vehicle_type,
                0
            ) + 1
        )

    for vehicle_type in [
        "car",
        "motorcycle",
        "bus",
        "truck",
        "auto",
    ]:

        print(
            f"{vehicle_type.capitalize():<15}: "
            f"{final_type_counts.get(vehicle_type, 0)}"
        )

    print()

    # ========================================================
    # PRESSURE STATISTICS
    # ========================================================

    if pressure_values:

        average_pressure = (
            sum(pressure_values) /
            len(pressure_values)
        )

        minimum_pressure = min(
            pressure_values
        )

        maximum_pressure = max(
            pressure_values
        )

    else:

        average_pressure = 0.0

        minimum_pressure = 0.0

        maximum_pressure = 0.0

    print("TRAFFIC PRESSURE")
    print("-" * 70)

    print(
        f"Average Pressure   : "
        f"{average_pressure:.2f}/100"
    )

    print(
        f"Minimum Pressure   : "
        f"{minimum_pressure:.2f}/100"
    )

    print(
        f"Maximum Pressure   : "
        f"{maximum_pressure:.2f}/100"
    )

    print(
        f"Peak Pressure      : "
        f"{peak_pressure:.2f}/100"
    )

    print(
        f"Peak Frame         : "
        f"{peak_frame}"
    )

    print(
        f"Peak Time          : "
        f"{peak_time:.2f} sec"
    )

    print()

    # ========================================================
    # TRAFFIC DISTRIBUTION
    # ========================================================

    print("TRAFFIC LEVEL DISTRIBUTION")
    print("-" * 70)

    total_processed = max(
        frame_number,
        1
    )

    for level in [
        "LOW",
        "MEDIUM",
        "HIGH",
        "CRITICAL",
    ]:

        count = traffic_levels[
            level
        ]

        percentage = (
            count /
            total_processed
        ) * 100

        print(
            f"{level:<10}: "
            f"{count:<4} "
            f"({percentage:.1f}%)"
        )

    # ========================================================
    # FINAL STATE
    # ========================================================

    if pressure_values:

        final_result = (
            result_data
        )

        print()

        print("FINAL TRAFFIC STATE")
        print("-" * 70)

        print(
            f"Final Pressure     : "
            f"{final_result['pressure']:.2f}/100"
        )

        print(
            f"Final Traffic Level: "
            f"{final_result['traffic_level']}"
        )

        print()

        # -----------------------------------------------
        # Components
        # -----------------------------------------------

        print("FINAL COMPONENTS")
        print("-" * 70)

        print(
            f"Vehicle Load Score  : "
            f"{final_result['vehicle_load_score']:.2f}"
        )

        print(
            f"Occupancy Score     : "
            f"{final_result['occupancy_score']:.2f}"
        )

        print(
            f"Queue Score         : "
            f"{final_result['queue_score']:.2f}"
        )

        print(
            f"Waiting Time Score   : "
            f"{final_result['waiting_time_score']:.2f}"
        )

        print(
            f"Arrival Rate Score   : "
            f"{final_result['arrival_rate_score']:.2f}"
        )

        print()

        # -----------------------------------------------
        # Queue
        # -----------------------------------------------

        print("QUEUE")
        print("-" * 70)

        print(
            f"Queue Length        : "
            f"{final_result['queue_length']}"
        )

        print(
            f"Moving Vehicles     : "
            f"{final_result['moving_vehicles']}"
        )

        print(
            f"Slow Vehicles       : "
            f"{final_result['slow_vehicles']}"
        )

        print(
            f"Stationary Vehicles : "
            f"{final_result['stationary_vehicles']}"
        )

        print(
            f"Average Waiting     : "
            f"{final_result['average_waiting_time']:.2f} sec"
        )

        print(
            f"Maximum Waiting     : "
            f"{final_result['maximum_waiting_time']:.2f} sec"
        )

        print()

        # -----------------------------------------------
        # Arrival
        # -----------------------------------------------

        print("ARRIVAL RATE")
        print("-" * 70)

        print(
            f"Arrival Count       : "
            f"{final_result['arrival_count']}"
        )

        print(
            f"Arrival Rate        : "
            f"{final_result['arrival_rate']:.2f} vehicles/min"
        )

        print(
            f"Arrival Status      : "
            f"{final_result['arrival_status']}"
        )

    print()
    print("=" * 70)
    print("PERSISTENT CCTV TRAFFIC V3 TEST COMPLETE")
    print("=" * 70)
    print()


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()