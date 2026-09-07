"""
Queue Detector V3

Detects:
- queued vehicles
- moving vehicles
- slow vehicles
- stationary vehicles
- waiting time

Uses persistent vehicle trajectories.

Prototype implementation.
"""

import math
from collections import Counter


class QueueDetector:

    def __init__(
        self,
        queue_zone_y_start=0.48,
        queue_zone_y_end=0.78,
        slow_speed_threshold=8.0,
        stationary_speed_threshold=3.0,
        minimum_wait_frames=15,
    ):

        self.queue_zone_y_start = (
            queue_zone_y_start
        )

        self.queue_zone_y_end = (
            queue_zone_y_end
        )

        self.slow_speed_threshold = (
            slow_speed_threshold
        )

        self.stationary_speed_threshold = (
            stationary_speed_threshold
        )

        self.minimum_wait_frames = (
            minimum_wait_frames
        )

    # ========================================================
    # QUEUE ZONE
    # ========================================================

    def is_in_queue_zone(
        self,
        vehicle,
        frame_height,
    ):

        if frame_height <= 0:
            return False

        bbox = vehicle.get(
            "bbox",
            []
        )

        if not bbox or len(bbox) != 4:
            return False

        x1, y1, x2, y2 = bbox

        center_y = (
            y1 + y2
        ) / 2.0

        normalized_y = (
            center_y /
            frame_height
        )

        return (
            self.queue_zone_y_start
            <= normalized_y
            <=
            self.queue_zone_y_end
        )

    # ========================================================
    # SPEED
    # ========================================================

    def calculate_speed(
        self,
        trajectory,
    ):

        if not trajectory:
            return 0.0

        if len(trajectory) < 2:
            return 0.0

        p1 = trajectory[-2]
        p2 = trajectory[-1]

        try:

            x1, y1 = p1
            x2, y2 = p2

        except (
            TypeError,
            ValueError,
        ):

            return 0.0

        dx = x2 - x1
        dy = y2 - y1

        distance = math.sqrt(
            dx * dx +
            dy * dy
        )

        return distance

    # ========================================================
    # MOVEMENT CLASSIFICATION
    # ========================================================

    def classify_movement(
        self,
        speed,
    ):

        if speed <= self.stationary_speed_threshold:

            return "STATIONARY"

        elif speed <= self.slow_speed_threshold:

            return "SLOW"

        else:

            return "MOVING"

    # ========================================================
    # WAITING FRAMES
    # ========================================================

    def estimate_wait_frames(
        self,
        trajectory,
    ):

        if not trajectory:
            return 0

        if len(trajectory) < 2:
            return 0

        wait_frames = 0

        # Start from newest point
        # and move backwards.

        for i in range(
            len(trajectory) - 1,
            0,
            -1,
        ):

            p1 = trajectory[i - 1]
            p2 = trajectory[i]

            try:

                x1, y1 = p1
                x2, y2 = p2

            except (
                TypeError,
                ValueError,
            ):

                break

            dx = x2 - x1
            dy = y2 - y1

            speed = math.sqrt(
                dx * dx +
                dy * dy
            )

            if speed <= self.slow_speed_threshold:

                wait_frames += 1

            else:

                break

        return wait_frames

    # ========================================================
    # WAITING SECONDS
    # ========================================================

    def calculate_waiting_seconds(
        self,
        wait_frames,
        fps,
    ):

        if fps <= 0:
            return 0.0

        return (
            wait_frames /
            fps
        )

    # ========================================================
    # QUEUED
    # ========================================================

    def is_queued(
        self,
        vehicle,
        frame_height,
    ):

        if not self.is_in_queue_zone(
            vehicle,
            frame_height,
        ):

            return False

        trajectory = vehicle.get(
            "trajectory",
            []
        )

        speed = self.calculate_speed(
            trajectory
        )

        wait_frames = (
            self.estimate_wait_frames(
                trajectory
            )
        )

        movement = (
            self.classify_movement(
                speed
            )
        )

        if movement not in (
            "STATIONARY",
            "SLOW",
        ):

            return False

        return (
            wait_frames
            >=
            self.minimum_wait_frames
        )

    # ========================================================
    # ANALYZE
    # ========================================================

    def analyze(
        self,
        vehicles,
        frame_height,
        fps,
    ):

        vehicles = vehicles or []

        queued_vehicles = []

        moving_vehicles = 0

        slow_vehicles = 0

        stationary_vehicles = 0

        waiting_times = []

        queue_types = Counter()

        # ----------------------------------------------------
        # Analyze every active vehicle
        # ----------------------------------------------------

        for vehicle in vehicles:

            trajectory = vehicle.get(
                "trajectory",
                []
            )

            speed = self.calculate_speed(
                trajectory
            )

            movement = (
                self.classify_movement(
                    speed
                )
            )

            # -----------------------------------------------
            # Movement counts
            # -----------------------------------------------

            if movement == "MOVING":

                moving_vehicles += 1

            elif movement == "SLOW":

                slow_vehicles += 1

            elif movement == "STATIONARY":

                stationary_vehicles += 1

            # -----------------------------------------------
            # Waiting
            # -----------------------------------------------

            wait_frames = (
                self.estimate_wait_frames(
                    trajectory
                )
            )

            wait_seconds = (
                self.calculate_waiting_seconds(
                    wait_frames,
                    fps,
                )
            )

            # -----------------------------------------------
            # Queue
            # -----------------------------------------------

            if self.is_queued(
                vehicle,
                frame_height,
            ):

                queued_vehicles.append(
                    vehicle
                )

                vehicle_type = vehicle.get(
                    "type",
                    vehicle.get(
                        "class",
                        "unknown"
                    )
                )

                queue_types[
                    vehicle_type
                ] += 1

                waiting_times.append(
                    wait_seconds
                )

        # ----------------------------------------------------
        # Queue statistics
        # ----------------------------------------------------

        queue_length = len(
            queued_vehicles
        )

        if waiting_times:

            average_waiting_time = (
                sum(waiting_times)
                /
                len(waiting_times)
            )

            maximum_waiting_time = max(
                waiting_times
            )

        else:

            average_waiting_time = 0.0

            maximum_waiting_time = 0.0

        # ----------------------------------------------------
        # Queue zone
        # ----------------------------------------------------

        queue_zone = {

            "y_start": (
                self.queue_zone_y_start
            ),

            "y_end": (
                self.queue_zone_y_end
            ),
        }

        # ----------------------------------------------------
        # Return canonical schema
        # ----------------------------------------------------

        return {

            "queue_length": (
                queue_length
            ),

            "queued_vehicles": (
                queued_vehicles
            ),

            "moving_vehicles": (
                moving_vehicles
            ),

            "slow_vehicles": (
                slow_vehicles
            ),

            "stationary_vehicles": (
                stationary_vehicles
            ),

            "average_waiting_time": (
                average_waiting_time
            ),

            "maximum_waiting_time": (
                maximum_waiting_time
            ),

            "queue_vehicle_types": (
                dict(queue_types)
            ),

            "queue_zone": (
                queue_zone
            ),
        }


# ============================================================
# STANDALONE TEST
# ============================================================

if __name__ == "__main__":

    print()
    print("=" * 70)
    print("QUEUE DETECTOR V3 - STANDALONE TEST")
    print("=" * 70)

    detector = QueueDetector()

    # Synthetic stationary vehicle
    vehicle_1 = {

        "id": 1,

        "type": "car",

        "bbox": [
            400,
            400,
            500,
            500,
        ],

        "trajectory": [
            [450, 450],
            [450, 451],
            [450, 451],
            [450, 452],
            [450, 452],
            [450, 453],
            [450, 453],
            [450, 454],
            [450, 454],
            [450, 455],
            [450, 455],
            [450, 456],
            [450, 456],
            [450, 457],
            [450, 457],
            [450, 458],
            [450, 458],
            [450, 459],
            [450, 459],
            [450, 460],
        ],
    }

    # Synthetic moving vehicle
    vehicle_2 = {

        "id": 2,

        "type": "car",

        "bbox": [
            300,
            250,
            400,
            350,
        ],

        "trajectory": [
            [300, 300],
            [310, 300],
            [320, 300],
            [330, 300],
            [340, 300],
        ],
    }

    vehicles = [
        vehicle_1,
        vehicle_2,
    ]

    result = detector.analyze(
        vehicles,
        frame_height=720,
        fps=30,
    )

    print()

    print(
        f"Queue Length        : "
        f"{result['queue_length']}"
    )

    print(
        f"Moving Vehicles     : "
        f"{result['moving_vehicles']}"
    )

    print(
        f"Slow Vehicles       : "
        f"{result['slow_vehicles']}"
    )

    print(
        f"Stationary Vehicles : "
        f"{result['stationary_vehicles']}"
    )

    print(
        f"Average Waiting     : "
        f"{result['average_waiting_time']:.2f} sec"
    )

    print(
        f"Maximum Waiting     : "
        f"{result['maximum_waiting_time']:.2f} sec"
    )

    print()

    print(
        "Queue vehicle types:"
    )

    for vehicle_type, count in (
        result[
            "queue_vehicle_types"
        ].items()
    ):

        print(
            f"  {vehicle_type}: {count}"
        )

    print()
    print("=" * 70)
    print("QUEUE DETECTOR V3 TEST COMPLETE")
    print("=" * 70)