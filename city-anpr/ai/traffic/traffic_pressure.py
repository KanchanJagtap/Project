"""
Traffic Pressure Engine V3

Purpose:
- Calculate intelligent traffic pressure from vehicle detections/tracks.
- Use vehicle type weights.
- Consider road occupancy.
- Consider queue length.
- Consider waiting time.
- Consider vehicle arrival rate.
- Maintain stable vehicle type information.
- Maintain rolling arrival events.
- Separate active vehicles from unique tracked vehicles.
- Smooth pressure using EMA.
- Work with QueueDetector.

Prototype only.
"""

from collections import Counter, deque
from ai.traffic.queue_detector import QueueDetector


class TrafficPressureEngine:
    """
    Traffic Pressure Engine V3

    Main inputs:
        active_vehicles
        vehicle_history
        current_frame
        fps
        frame_width
        frame_height

    Main output:
        Intelligent traffic pressure score from 0-100.
    """

    # ---------------------------------------------------------
    # VEHICLE WEIGHTS
    # ---------------------------------------------------------

    VEHICLE_WEIGHTS = {
        "motorcycle": 1.0,
        "car": 1.5,
        "auto": 1.5,
        "bus": 4.0,
        "truck": 4.0,
    }

    # ---------------------------------------------------------
    # PRESSURE COMPONENT WEIGHTS
    # ---------------------------------------------------------

    COMPONENT_WEIGHTS = {
        "vehicle_load": 0.25,
        "road_occupancy": 0.25,
        "queue_length": 0.20,
        "waiting_time": 0.15,
        "arrival_rate": 0.15,
    }

    # ---------------------------------------------------------
    # DEFAULT NORMALIZATION LIMITS
    # ---------------------------------------------------------

    DEFAULT_ROAD_CAPACITY = 40

    DEFAULT_MAX_QUEUE_LENGTH = 20

    DEFAULT_MAX_WAITING_TIME = 120

    DEFAULT_MAX_ARRIVAL_RATE = 30

    # ---------------------------------------------------------
    # ARRIVAL WINDOW
    # ---------------------------------------------------------

    ARRIVAL_WINDOW_SECONDS = 10

    # ---------------------------------------------------------
    # EMA SMOOTHING
    # ---------------------------------------------------------

    SMOOTHING_ALPHA = 0.25

    # ---------------------------------------------------------
    # TRAJECTORY LIMIT
    # ---------------------------------------------------------

    MAX_TRAJECTORY_LENGTH = 100

    def __init__(
        self,
        road_capacity=DEFAULT_ROAD_CAPACITY,
        max_queue_length=DEFAULT_MAX_QUEUE_LENGTH,
        max_waiting_time=DEFAULT_MAX_WAITING_TIME,
        max_arrival_rate=DEFAULT_MAX_ARRIVAL_RATE,
        smoothing_alpha=SMOOTHING_ALPHA,
    ):
        self.road_capacity = road_capacity
        self.max_queue_length = max_queue_length
        self.max_waiting_time = max_waiting_time
        self.max_arrival_rate = max_arrival_rate

        self.smoothing_alpha = smoothing_alpha

        # Queue detector
        #
        # Initial ROI tuned for the supplied traffic.mp4.
        #
        # This is a prototype ROI and should eventually be
        # configurable per CCTV camera.
        self.queue_detector = QueueDetector(
            queue_zone_y_start=0.48,
            queue_zone_y_end=0.78,
            slow_speed_threshold=8,
            stationary_speed_threshold=3,
            minimum_wait_frames=15,
        )

        # EMA state
        self.smoothed_pressure = None

        # Arrival events
        #
        # Stores:
        #     (frame_number, vehicle_id)
        #
        # Used for rolling arrival-rate calculation.
        self.arrival_events = deque()

        # Vehicles whose first appearance has already been
        # registered as an arrival event.
        self.registered_arrivals = set()

    # =========================================================
    # VEHICLE LOAD
    # =========================================================

    def calculate_vehicle_load(self, vehicles):
        """
        Calculate weighted vehicle load.

        Example:
            motorcycle = 1.0
            car        = 1.5
            auto       = 1.5
            bus        = 4.0
            truck      = 4.0
        """

        total_load = 0.0

        for vehicle in vehicles:

            vehicle_type = vehicle.get(
                "type",
                vehicle.get("class", "car")
            )

            weight = self.VEHICLE_WEIGHTS.get(
                vehicle_type,
                1.5
            )

            total_load += weight

        return total_load

    # =========================================================
    # VEHICLE LOAD SCORE
    # =========================================================

    def calculate_vehicle_load_score(self, vehicle_load):
        """
        Convert weighted vehicle load to 0-100 score.
        """

        maximum_load = self.road_capacity * 1.5

        if maximum_load <= 0:
            return 0.0

        score = (
            vehicle_load /
            maximum_load
        ) * 100

        return min(
            max(score, 0.0),
            100.0
        )

    # =========================================================
    # ROAD OCCUPANCY
    # =========================================================

    def calculate_road_occupancy(
        self,
        vehicles,
        frame_width,
        frame_height,
    ):
        """
        Estimate road occupancy from bounding-box area.

        This is an approximation.

        It is NOT a true road-segmentation occupancy model.
        """

        if frame_width <= 0 or frame_height <= 0:
            return 0.0

        frame_area = (
            frame_width *
            frame_height
        )

        total_vehicle_area = 0.0

        for vehicle in vehicles:

            bbox = vehicle.get("bbox")

            if not bbox or len(bbox) != 4:
                continue

            x1, y1, x2, y2 = bbox

            width = max(
                0,
                x2 - x1
            )

            height = max(
                0,
                y2 - y1
            )

            area = width * height

            total_vehicle_area += area

        occupancy = (
            total_vehicle_area /
            frame_area
        ) * 100

        return min(
            max(occupancy, 0.0),
            100.0
        )

    # =========================================================
    # ROAD OCCUPANCY SCORE
    # =========================================================

    def calculate_occupancy_score(
        self,
        occupancy,
    ):
        """
        30% bbox occupancy is treated as 100 pressure.
        """

        score = (
            occupancy /
            30.0
        ) * 100

        return min(
            max(score, 0.0),
            100.0
        )

    # =========================================================
    # QUEUE
    # =========================================================

    def calculate_queue(
        self,
        vehicles,
        frame_height,
        fps,
    ):
        """
        Run QueueDetector.

        Returns a normalized queue result.

        This method also handles compatibility with
        different QueueDetector output key names.
        """

        queue_result = self.queue_detector.analyze(
            vehicles,
            frame_height,
            fps,
        )

        # -----------------------------------------------------
        # NORMALIZE KEY NAMES
        # -----------------------------------------------------

        queue_length = queue_result.get(
            "queue_length",
            queue_result.get(
                "queued_count",
                0
            )
        )

        queued_vehicles = queue_result.get(
            "queued_vehicles",
            []
        )

        moving_vehicles = queue_result.get(
            "moving_vehicles",
            queue_result.get(
                "moving",
                0
            )
        )

        slow_vehicles = queue_result.get(
            "slow_vehicles",
            queue_result.get(
                "slow",
                0
            )
        )

        stationary_vehicles = queue_result.get(
            "stationary_vehicles",
            queue_result.get(
                "stationary",
                0
            )
        )

        average_waiting_time = queue_result.get(
            "average_waiting_time",
            queue_result.get(
                "avg_waiting_time",
                0.0
            )
        )

        maximum_waiting_time = queue_result.get(
            "maximum_waiting_time",
            queue_result.get(
                "max_waiting_time",
                0.0
            )
        )

        queue_vehicle_types = queue_result.get(
            "queue_vehicle_types",
            {}
        )

        queue_zone = queue_result.get(
            "queue_zone",
            {}
        )

        return {
            "queue_length": queue_length,
            "queued_vehicles": queued_vehicles,
            "moving_vehicles": moving_vehicles,
            "slow_vehicles": slow_vehicles,
            "stationary_vehicles": stationary_vehicles,
            "average_waiting_time": average_waiting_time,
            "maximum_waiting_time": maximum_waiting_time,
            "queue_vehicle_types": queue_vehicle_types,
            "queue_zone": queue_zone,
        }

    # =========================================================
    # QUEUE SCORE
    # =========================================================

    def calculate_queue_score(
        self,
        queue_length,
    ):
        """
        Convert queue length to 0-100 score.
        """

        if self.max_queue_length <= 0:
            return 0.0

        score = (
            queue_length /
            self.max_queue_length
        ) * 100

        return min(
            max(score, 0.0),
            100.0
        )

    # =========================================================
    # WAITING TIME SCORE
    # =========================================================

    def calculate_waiting_time_score(
        self,
        waiting_time,
    ):
        """
        Convert waiting time to 0-100 score.
        """

        if self.max_waiting_time <= 0:
            return 0.0

        score = (
            waiting_time /
            self.max_waiting_time
        ) * 100

        return min(
            max(score, 0.0),
            100.0
        )

    # =========================================================
    # VEHICLE TYPE STABILITY
    # =========================================================

    def get_stable_vehicle_type(
        self,
        vehicle,
    ):
        """
        Return the most reliable vehicle type.

        If a vehicle contains:
            type_history = [...]

        majority voting is used.

        Otherwise the current type is returned.
        """

        type_history = vehicle.get(
            "type_history",
            []
        )

        if type_history:

            valid_types = [
                vehicle_type
                for vehicle_type in type_history
                if vehicle_type in self.VEHICLE_WEIGHTS
            ]

            if valid_types:

                counter = Counter(
                    valid_types
                )

                return counter.most_common(1)[0][0]

        return vehicle.get(
            "type",
            vehicle.get(
                "class",
                "car"
            )
        )

    # =========================================================
    # UPDATE VEHICLE HISTORY
    # =========================================================

    def update_vehicle_history(
        self,
        vehicle_history,
        active_vehicles,
        current_frame,
    ):
        """
        Update persistent vehicle history.

        Expected active vehicle format:

        {
            "id": 10,
            "type": "car",
            "confidence": 0.91,
            "bbox": [x1,y1,x2,y2]
        }
        """

        for vehicle in active_vehicles:

            vehicle_id = vehicle.get("id")

            if vehicle_id is None:
                continue

            vehicle_type = vehicle.get(
                "type",
                vehicle.get(
                    "class",
                    "car"
                )
            )

            confidence = float(
                vehicle.get(
                    "confidence",
                    0.0
                )
            )

            bbox = vehicle.get(
                "bbox",
                []
            )

            # -------------------------------------------------
            # NEW VEHICLE
            # -------------------------------------------------

            if vehicle_id not in vehicle_history:

                vehicle_history[vehicle_id] = {
                    "id": vehicle_id,
                    "type": vehicle_type,
                    "type_history": [
                        vehicle_type
                    ],
                    "first_seen": current_frame,
                    "last_seen": current_frame,
                    "frames_tracked": 1,
                    "best_confidence": confidence,
                    "bbox": bbox,
                    "center": [],
                    "trajectory": [],
                }

                # Register arrival
                if vehicle_id not in self.registered_arrivals:

                    self.arrival_events.append(
                        (
                            current_frame,
                            vehicle_id
                        )
                    )

                    self.registered_arrivals.add(
                        vehicle_id
                    )

            # -------------------------------------------------
            # EXISTING VEHICLE
            # -------------------------------------------------

            else:

                history = vehicle_history[
                    vehicle_id
                ]

                history["last_seen"] = current_frame

                history["frames_tracked"] += 1

                history["best_confidence"] = max(
                    history.get(
                        "best_confidence",
                        0.0
                    ),
                    confidence,
                )

                # ---------------------------------------------
                # TYPE HISTORY
                # ---------------------------------------------

                history.setdefault(
                    "type_history",
                    []
                )

                history["type_history"].append(
                    vehicle_type
                )

                # Keep only recent type observations
                if len(
                    history["type_history"]
                ) > 30:

                    history[
                        "type_history"
                    ] = history[
                        "type_history"
                    ][-30:]

                # Stable type
                history["type"] = (
                    self.get_stable_vehicle_type(
                        history
                    )
                )

                # ---------------------------------------------
                # BBOX
                # ---------------------------------------------

                history["bbox"] = bbox

            # -------------------------------------------------
            # CENTER
            # -------------------------------------------------

            if bbox and len(bbox) == 4:

                x1, y1, x2, y2 = bbox

                center_x = int(
                    (x1 + x2) / 2
                )

                center_y = int(
                    (y1 + y2) / 2
                )

                center = [
                    center_x,
                    center_y
                ]

                history = vehicle_history[
                    vehicle_id
                ]

                history["center"] = center

                history.setdefault(
                    "trajectory",
                    []
                )

                history[
                    "trajectory"
                ].append(
                    center
                )

                # Limit trajectory size
                if len(
                    history["trajectory"]
                ) > self.MAX_TRAJECTORY_LENGTH:

                    history[
                        "trajectory"
                    ] = history[
                        "trajectory"
                    ][
                        -self.MAX_TRAJECTORY_LENGTH:
                    ]

    # =========================================================
    # ROLLING ARRIVAL EVENTS
    # =========================================================

    def update_arrival_events(
        self,
        current_frame,
        fps,
    ):
        """
        Remove arrival events older than the rolling window.
        """

        if fps <= 0:
            return

        window_frames = int(
            fps *
            self.ARRIVAL_WINDOW_SECONDS
        )

        minimum_frame = (
            current_frame -
            window_frames
        )

        while self.arrival_events:

            frame_number, vehicle_id = (
                self.arrival_events[0]
            )

            if frame_number < minimum_frame:

                self.arrival_events.popleft()

            else:

                break

    # =========================================================
    # ARRIVAL RATE
    # =========================================================

    def calculate_arrival_rate(
        self,
        current_frame,
        fps,
    ):
        """
        Calculate vehicles/minute using rolling arrivals.

        During the first ARRIVAL_WINDOW_SECONDS,
        return warm-up status.
        """

        if fps <= 0:
            return {
                "arrival_count": 0,
                "arrival_rate": 0.0,
                "status": "INVALID_FPS",
            }

        elapsed_seconds = (
            current_frame /
            fps
        )

        # ---------------------------------------------
        # WARM-UP
        # ---------------------------------------------

        if elapsed_seconds < self.ARRIVAL_WINDOW_SECONDS:

            return {
                "arrival_count": len(
                    self.arrival_events
                ),
                "arrival_rate": 0.0,
                "status": "WARM-UP",
            }

        # ---------------------------------------------
        # ROLLING WINDOW
        # ---------------------------------------------

        self.update_arrival_events(
            current_frame,
            fps,
        )

        arrival_count = len(
            self.arrival_events
        )

        arrival_rate = (
            arrival_count /
            self.ARRIVAL_WINDOW_SECONDS
        ) * 60

        return {
            "arrival_count": arrival_count,
            "arrival_rate": arrival_rate,
            "status": "ACTIVE",
        }

    # =========================================================
    # ARRIVAL RATE SCORE
    # =========================================================

    def calculate_arrival_rate_score(
        self,
        arrival_rate,
    ):
        """
        Convert vehicles/minute to 0-100 score.
        """

        if self.max_arrival_rate <= 0:
            return 0.0

        score = (
            arrival_rate /
            self.max_arrival_rate
        ) * 100

        return min(
            max(score, 0.0),
            100.0
        )

    # =========================================================
    # EMA SMOOTHING
    # =========================================================

    def smooth_pressure(
        self,
        raw_pressure,
    ):
        """
        Exponential moving average.
        """

        if self.smoothed_pressure is None:

            self.smoothed_pressure = (
                raw_pressure
            )

        else:

            self.smoothed_pressure = (
                self.smoothing_alpha *
                raw_pressure
                +
                (1 -
                 self.smoothing_alpha)
                *
                self.smoothed_pressure
            )

        return self.smoothed_pressure

    # =========================================================
    # TRAFFIC LEVEL
    # =========================================================

    def get_traffic_level(
        self,
        pressure,
    ):
        """
        Convert pressure to traffic level.
        """

        if pressure < 25:
            return "LOW"

        elif pressure < 50:
            return "MEDIUM"

        elif pressure < 75:
            return "HIGH"

        else:
            return "CRITICAL"

    # =========================================================
    # MAIN CALCULATION
    # =========================================================

    def calculate_pressure(
        self,
        active_vehicles,
        vehicle_history,
        current_frame,
        fps,
        frame_width,
        frame_height,
    ):
        """
        Main traffic pressure calculation.
        """

        # -----------------------------------------------------
        # ACTIVE VEHICLES
        # -----------------------------------------------------

        active_vehicles = (
            active_vehicles or []
        )

        # -----------------------------------------------------
        # UPDATE HISTORY
        # -----------------------------------------------------

        self.update_vehicle_history(
            vehicle_history,
            active_vehicles,
            current_frame,
        )

        # -----------------------------------------------------
        # STABLE ACTIVE VEHICLE DATA
        # -----------------------------------------------------

        stable_active_vehicles = []

        for vehicle in active_vehicles:

            vehicle_id = vehicle.get(
                "id"
            )

            if vehicle_id in vehicle_history:

                history = vehicle_history[
                    vehicle_id
                ]

                stable_vehicle = dict(
                    vehicle
                )

                stable_vehicle["type"] = (
                    history.get(
                        "type",
                        vehicle.get(
                            "type",
                            "car"
                        )
                    )
                )

                stable_vehicle["trajectory"] = (
                    history.get(
                        "trajectory",
                        []
                    )
                )

                stable_vehicle["first_seen"] = (
                    history.get(
                        "first_seen",
                        current_frame
                    )
                )

                stable_vehicle["last_seen"] = (
                    history.get(
                        "last_seen",
                        current_frame
                    )
                )

                stable_active_vehicles.append(
                    stable_vehicle
                )

            else:

                stable_active_vehicles.append(
                    vehicle
                )

        # -----------------------------------------------------
        # VEHICLE LOAD
        # -----------------------------------------------------

        vehicle_load = (
            self.calculate_vehicle_load(
                stable_active_vehicles
            )
        )

        vehicle_load_score = (
            self.calculate_vehicle_load_score(
                vehicle_load
            )
        )

        # -----------------------------------------------------
        # OCCUPANCY
        # -----------------------------------------------------

        occupancy = (
            self.calculate_road_occupancy(
                stable_active_vehicles,
                frame_width,
                frame_height,
            )
        )

        occupancy_score = (
            self.calculate_occupancy_score(
                occupancy
            )
        )

        # -----------------------------------------------------
        # QUEUE
        # -----------------------------------------------------

        queue_result = (
            self.calculate_queue(
                stable_active_vehicles,
                frame_height,
                fps,
            )
        )

        queue_length = queue_result[
            "queue_length"
        ]

        queue_score = (
            self.calculate_queue_score(
                queue_length
            )
        )

        average_waiting_time = (
            queue_result[
                "average_waiting_time"
            ]
        )

        maximum_waiting_time = (
            queue_result[
                "maximum_waiting_time"
            ]
        )

        waiting_time_score = (
            self.calculate_waiting_time_score(
                average_waiting_time
            )
        )

        # -----------------------------------------------------
        # ARRIVAL RATE
        # -----------------------------------------------------

        arrival_result = (
            self.calculate_arrival_rate(
                current_frame,
                fps,
            )
        )

        arrival_count = arrival_result[
            "arrival_count"
        ]

        arrival_rate = arrival_result[
            "arrival_rate"
        ]

        arrival_status = arrival_result[
            "status"
        ]

        # During warm-up arrival contribution is zero.
        if arrival_status == "WARM-UP":

            arrival_rate_score = 0.0

        else:

            arrival_rate_score = (
                self.calculate_arrival_rate_score(
                    arrival_rate
                )
            )

        # -----------------------------------------------------
        # RAW PRESSURE
        # -----------------------------------------------------

        raw_pressure = (

            self.COMPONENT_WEIGHTS[
                "vehicle_load"
            ]
            *
            vehicle_load_score

            +

            self.COMPONENT_WEIGHTS[
                "road_occupancy"
            ]
            *
            occupancy_score

            +

            self.COMPONENT_WEIGHTS[
                "queue_length"
            ]
            *
            queue_score

            +

            self.COMPONENT_WEIGHTS[
                "waiting_time"
            ]
            *
            waiting_time_score

            +

            self.COMPONENT_WEIGHTS[
                "arrival_rate"
            ]
            *
            arrival_rate_score
        )

        raw_pressure = min(
            max(raw_pressure, 0.0),
            100.0
        )

        # -----------------------------------------------------
        # SMOOTHED PRESSURE
        # -----------------------------------------------------

        smoothed_pressure = (
            self.smooth_pressure(
                raw_pressure
            )
        )

        traffic_level = (
            self.get_traffic_level(
                smoothed_pressure
            )
        )

        # -----------------------------------------------------
        # UNIQUE VEHICLE COUNT
        # -----------------------------------------------------

        unique_vehicle_count = len(
            vehicle_history
        )

        # -----------------------------------------------------
        # UNIQUE TYPE COUNTS
        # -----------------------------------------------------

        unique_type_counts = Counter()

        for vehicle in vehicle_history.values():

            vehicle_type = (
                vehicle.get(
                    "type",
                    "car"
                )
            )

            unique_type_counts[
                vehicle_type
            ] += 1

        # -----------------------------------------------------
        # RETURN RESULT
        # -----------------------------------------------------

        return {

            # ---------------------------------------------
            # PRESSURE
            # ---------------------------------------------

            "pressure": round(
                smoothed_pressure,
                2
            ),

            "raw_pressure": round(
                raw_pressure,
                2
            ),

            "traffic_level": (
                traffic_level
            ),

            # ---------------------------------------------
            # ACTIVE / UNIQUE
            # ---------------------------------------------

            "active_vehicle_count": len(
                stable_active_vehicles
            ),

            "unique_vehicle_count": (
                unique_vehicle_count
            ),

            "unique_vehicle_types": dict(
                unique_type_counts
            ),

            # ---------------------------------------------
            # VEHICLE LOAD
            # ---------------------------------------------

            "vehicle_load": round(
                vehicle_load,
                2
            ),

            "vehicle_load_score": round(
                vehicle_load_score,
                2
            ),

            # ---------------------------------------------
            # OCCUPANCY
            # ---------------------------------------------

            "road_occupancy": round(
                occupancy,
                2
            ),

            "occupancy_score": round(
                occupancy_score,
                2
            ),

            # ---------------------------------------------
            # QUEUE
            # ---------------------------------------------

            "queue_length": (
                queue_length
            ),

            "queue_score": round(
                queue_score,
                2
            ),

            "queued_vehicles": (
                queue_result[
                    "queued_vehicles"
                ]
            ),

            "queue_vehicle_types": (
                queue_result[
                    "queue_vehicle_types"
                ]
            ),

            "queue_zone": (
                queue_result[
                    "queue_zone"
                ]
            ),

            # ---------------------------------------------
            # MOVEMENT
            # ---------------------------------------------

            "moving_vehicles": (
                queue_result.get(
                    "moving_vehicles",
                    0
                )
            ),

            "slow_vehicles": (
                queue_result.get(
                    "slow_vehicles",
                    0
                )
            ),

            "stationary_vehicles": (
                queue_result.get(
                    "stationary_vehicles",
                    0
                )
            ),

            # ---------------------------------------------
            # WAITING
            # ---------------------------------------------

            "average_waiting_time": round(
                average_waiting_time,
                2
            ),

            "maximum_waiting_time": round(
                maximum_waiting_time,
                2
            ),

            "waiting_time_score": round(
                waiting_time_score,
                2
            ),

            # ---------------------------------------------
            # ARRIVAL
            # ---------------------------------------------

            "arrival_count": (
                arrival_count
            ),

            "arrival_rate": round(
                arrival_rate,
                2
            ),

            "arrival_rate_score": round(
                arrival_rate_score,
                2
            ),

            "arrival_status": (
                arrival_status
            ),

            # ---------------------------------------------
            # COMPONENT WEIGHTS
            # ---------------------------------------------

            "component_weights": dict(
                self.COMPONENT_WEIGHTS
            ),
        }

    # =========================================================
    # REPORT
    # =========================================================

    def print_report(
        self,
        result,
    ):
        """
        Print formatted traffic pressure report.
        """

        print()
        print("=" * 70)
        print("TRAFFIC PRESSURE ENGINE V3")
        print("=" * 70)

        print()

        print(
            f"Traffic Pressure Score : "
            f"{result['pressure']:.2f}/100"
        )

        print(
            f"Raw Pressure Score     : "
            f"{result['raw_pressure']:.2f}/100"
        )

        print(
            f"Traffic Level          : "
            f"{result['traffic_level']}"
        )

        print()

        print("--- VEHICLES ---")

        print(
            f"Active Vehicles        : "
            f"{result['active_vehicle_count']}"
        )

        print(
            f"Unique Vehicles        : "
            f"{result['unique_vehicle_count']}"
        )

        print()

        print(
            "Unique Vehicle Types:"
        )

        for vehicle_type, count in (
            result[
                "unique_vehicle_types"
            ].items()
        ):

            print(
                f"  {vehicle_type}: {count}"
            )

        print()

        print("--- VEHICLE LOAD ---")

        print(
            f"Vehicle Load           : "
            f"{result['vehicle_load']:.2f}"
        )

        print(
            f"Vehicle Load Score     : "
            f"{result['vehicle_load_score']:.2f}/100"
        )

        print()

        print("--- ROAD OCCUPANCY ---")

        print(
            f"Road Occupancy         : "
            f"{result['road_occupancy']:.2f}%"
        )

        print(
            f"Occupancy Score        : "
            f"{result['occupancy_score']:.2f}/100"
        )

        print()

        print("--- QUEUE ---")

        print(
            f"Queue Length           : "
            f"{result['queue_length']}"
        )

        print(
            f"Queue Score            : "
            f"{result['queue_score']:.2f}/100"
        )

        print(
            f"Moving Vehicles        : "
            f"{result['moving_vehicles']}"
        )

        print(
            f"Slow Vehicles          : "
            f"{result['slow_vehicles']}"
        )

        print(
            f"Stationary Vehicles    : "
            f"{result['stationary_vehicles']}"
        )

        print()

        print(
            f"Average Waiting Time   : "
            f"{result['average_waiting_time']:.2f} sec"
        )

        print(
            f"Maximum Waiting Time   : "
            f"{result['maximum_waiting_time']:.2f} sec"
        )

        print(
            f"Waiting Time Score     : "
            f"{result['waiting_time_score']:.2f}/100"
        )

        print()

        print("--- ARRIVAL RATE ---")

        print(
            f"Arrival Count          : "
            f"{result['arrival_count']}"
        )

        print(
            f"Arrival Rate           : "
            f"{result['arrival_rate']:.2f} vehicles/min"
        )

        print(
            f"Arrival Rate Score     : "
            f"{result['arrival_rate_score']:.2f}/100"
        )

        print(
            f"Arrival Status         : "
            f"{result['arrival_status']}"
        )

        print()

        print("=" * 70)


# =============================================================
# STANDALONE TEST
# =============================================================

if __name__ == "__main__":

    print()
    print("=" * 70)
    print("TRAFFIC PRESSURE ENGINE V3 - STANDALONE TEST")
    print("=" * 70)

    # ---------------------------------------------------------
    # Synthetic vehicle history
    # ---------------------------------------------------------

    vehicle_history = {

        1: {
            "id": 1,
            "type": "car",
            "type_history": [
                "car",
                "car",
                "car",
            ],
            "first_seen": 1,
            "last_seen": 300,
            "frames_tracked": 300,
            "best_confidence": 0.92,
            "bbox": [
                400,
                400,
                500,
                500,
            ],
            "center": [
                450,
                450,
            ],
            "trajectory": [
                [450, 450],
                [451, 450],
            ],
        },

        2: {
            "id": 2,
            "type": "truck",
            "type_history": [
                "truck",
                "truck",
                "truck",
            ],
            "first_seen": 280,
            "last_seen": 300,
            "frames_tracked": 21,
            "best_confidence": 0.88,
            "bbox": [
                600,
                350,
                850,
                600,
            ],
            "center": [
                725,
                475,
            ],
            "trajectory": [
                [725, 475],
                [726, 475],
            ],
        },

        3: {
            "id": 3,
            "type": "motorcycle",
            "type_history": [
                "motorcycle",
                "motorcycle",
            ],
            "first_seen": 295,
            "last_seen": 300,
            "frames_tracked": 6,
            "best_confidence": 0.91,
            "bbox": [
                200,
                300,
                260,
                390,
            ],
            "center": [
                230,
                345,
            ],
            "trajectory": [
                [210, 340],
                [220, 342],
                [230, 345],
            ],
        },
    }

    # ---------------------------------------------------------
    # Active vehicles
    # ---------------------------------------------------------

    active_vehicles = [

        {
            "id": 1,
            "type": "car",
            "confidence": 0.92,
            "bbox": [
                400,
                400,
                500,
                500,
            ],
        },

        {
            "id": 2,
            "type": "truck",
            "confidence": 0.88,
            "bbox": [
                600,
                350,
                850,
                600,
            ],
        },

        {
            "id": 3,
            "type": "motorcycle",
            "confidence": 0.91,
            "bbox": [
                200,
                300,
                260,
                390,
            ],
        },
    ]

    # ---------------------------------------------------------
    # Engine
    # ---------------------------------------------------------

    engine = TrafficPressureEngine()

    # ---------------------------------------------------------
    # Simulate arrival events
    # ---------------------------------------------------------

    engine.arrival_events.append(
        (1, 1)
    )

    engine.arrival_events.append(
        (280, 2)
    )

    engine.arrival_events.append(
        (295, 3)
    )

    engine.registered_arrivals.update(
        {
            1,
            2,
            3,
        }
    )

    # ---------------------------------------------------------
    # Calculate
    # ---------------------------------------------------------

    result = engine.calculate_pressure(

        active_vehicles=active_vehicles,

        vehicle_history=vehicle_history,

        current_frame=300,

        fps=30,

        frame_width=1280,

        frame_height=720,
    )

    # ---------------------------------------------------------
    # Report
    # ---------------------------------------------------------

    engine.print_report(
        result
    )

    print()
    print(
        "Standalone V3 test complete."
    )
    print()