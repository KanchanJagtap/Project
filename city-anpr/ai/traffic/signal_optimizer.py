from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class ApproachState:
    """
    Traffic state for one intersection approach.

    All values are intended for the City-Wide AI Engine prototype.
    """

    approach_id: str
    traffic_pressure: float
    queue_length: int
    average_waiting_time: float
    arrival_rate: float
    starvation_time: float = 0.0
    emergency_priority: bool = False

    def __post_init__(self):
        self.traffic_pressure = max(0.0, min(100.0, float(self.traffic_pressure)))
        self.queue_length = max(0, int(self.queue_length))
        self.average_waiting_time = max(0.0, float(self.average_waiting_time))
        self.arrival_rate = max(0.0, float(self.arrival_rate))
        self.starvation_time = max(0.0, float(self.starvation_time))


@dataclass
class SignalDecision:
    """
    Optimization decision for one approach.
    """

    approach_id: str
    priority_score: float
    green_time: int
    reason: str


class SignalOptimizer:
    """
    Prototype signal optimization engine.

    The optimizer does NOT directly control real traffic signals.

    It calculates a recommended green-time allocation using:
        - Traffic pressure
        - Queue length
        - Waiting time
        - Arrival rate
        - Starvation protection
        - Emergency priority

    Prototype safety constraints:
        Minimum green       = 20 seconds
        Maximum green       = 60 seconds
        Yellow              = 3 seconds
        All-red clearance   = 2 seconds
        Target cycle        = 120 seconds
        Starvation threshold = 60 seconds
    """

    MIN_GREEN = 20
    MAX_GREEN = 60
    YELLOW_TIME = 3
    ALL_RED_TIME = 2
    TARGET_CYCLE = 120
    STARVATION_THRESHOLD = 60

    def __init__(self):
        self.current_phase: Optional[str] = None
        self.last_decisions: Dict[str, SignalDecision] = {}

    # ---------------------------------------------------------
    # Priority calculation
    # ---------------------------------------------------------

    def calculate_priority(self, approach: ApproachState) -> float:
        """
        Calculate optimization priority for an approach.

        Components:
            Traffic pressure : 40%
            Queue pressure   : 25%
            Waiting pressure  : 20%
            Arrival pressure : 10%
            Starvation bonus  : 5%

        Emergency priority overrides the normal score.
        """

        traffic_score = approach.traffic_pressure

        queue_score = min(
            (approach.queue_length / 20.0) * 100.0,
            100.0,
        )

        waiting_score = min(
            (approach.average_waiting_time / 60.0) * 100.0,
            100.0,
        )

        arrival_score = min(
            (approach.arrival_rate / 30.0) * 100.0,
            100.0,
        )

        starvation_score = min(
            (approach.starvation_time / self.STARVATION_THRESHOLD) * 100.0,
            100.0,
        )

        priority = (
            traffic_score * 0.40
            + queue_score * 0.25
            + waiting_score * 0.20
            + arrival_score * 0.10
            + starvation_score * 0.05
        )

        if approach.starvation_time >= self.STARVATION_THRESHOLD:
            priority += 15.0

        if approach.emergency_priority:
            priority = 100.0

        return min(priority, 100.0)

    # ---------------------------------------------------------
    # Green-time calculation
    # ---------------------------------------------------------

    def calculate_green_time(
        self,
        priority_score: float,
        total_priority: float,
    ) -> int:
        """
        Convert priority into a green-time recommendation.

        The result always remains within the configured
        minimum/maximum green limits.
        """

        if total_priority <= 0:
            return self.MIN_GREEN

        share = priority_score / total_priority

        available_green = (
            self.TARGET_CYCLE
            - self.YELLOW_TIME
            - self.ALL_RED_TIME
        )

        raw_green = self.MIN_GREEN + (
            share * (available_green - self.MIN_GREEN)
        )

        green_time = round(raw_green)

        return max(
            self.MIN_GREEN,
            min(self.MAX_GREEN, green_time),
        )

    # ---------------------------------------------------------
    # Emergency handling
    # ---------------------------------------------------------

    def handle_emergency(
        self,
        approaches: list[ApproachState],
    ) -> Optional[ApproachState]:
        """
        Find the highest-priority emergency approach.

        Emergency handling is deliberately limited to decision
        generation. It does not instantly terminate the current
        green phase.
        """

        emergencies = [
            approach
            for approach in approaches
            if approach.emergency_priority
        ]

        if not emergencies:
            return None

        return max(
            emergencies,
            key=lambda approach: self.calculate_priority(approach),
        )

    # ---------------------------------------------------------
    # Intersection optimization
    # ---------------------------------------------------------

    def optimize(
        self,
        approaches: list[ApproachState],
    ) -> list[SignalDecision]:
        """
        Optimize all intersection approaches together.

        This is intentionally a global intersection decision rather
        than independently extending each lane.
        """

        if not approaches:
            self.last_decisions = {}
            return []

        emergency = self.handle_emergency(approaches)

        priorities = {
            approach.approach_id: self.calculate_priority(approach)
            for approach in approaches
        }

        total_priority = sum(priorities.values())

        decisions = []

        for approach in approaches:
            priority = priorities[approach.approach_id]

            if emergency is not None:
                if approach.approach_id == emergency.approach_id:
                    green_time = self.MAX_GREEN
                    reason = (
                        "Emergency priority: highest-priority "
                        "emergency approach."
                    )
                else:
                    green_time = self.MIN_GREEN
                    reason = (
                        "Emergency active: minimum safe allocation "
                        "for non-emergency approach."
                    )
            else:
                green_time = self.calculate_green_time(
                    priority,
                    total_priority,
                )

                if approach.starvation_time >= self.STARVATION_THRESHOLD:
                    reason = "Starvation protection applied."
                elif priority >= 70:
                    reason = "High traffic priority."
                elif priority >= 40:
                    reason = "Medium traffic priority."
                else:
                    reason = "Normal traffic priority."

            decisions.append(
                SignalDecision(
                    approach_id=approach.approach_id,
                    priority_score=round(priority, 2),
                    green_time=green_time,
                    reason=reason,
                )
            )

        decisions.sort(
            key=lambda decision: decision.priority_score,
            reverse=True,
        )

        self.last_decisions = {
            decision.approach_id: decision
            for decision in decisions
        }

        return decisions

    # ---------------------------------------------------------
    # Safe phase transition
    # ---------------------------------------------------------

    def get_safe_transition(
        self,
        current_approach: Optional[str],
        next_approach: str,
    ) -> list[str]:
        """
        Return the safe prototype transition sequence.

        The optimizer never jumps directly from one green approach
        to another.

        Normal transition:

            GREEN(current)
                 ↓
            YELLOW
                 ↓
            ALL-RED
                 ↓
            GREEN(next)
        """

        if current_approach is None:
            return [
                f"GREEN({next_approach})",
            ]

        if current_approach == next_approach:
            return [
                f"GREEN({current_approach})",
            ]

        return [
            f"GREEN({current_approach})",
            f"YELLOW({current_approach})",
            "ALL-RED",
            f"GREEN({next_approach})",
        ]


# =============================================================
# Standalone test
# =============================================================

def run_standalone_test():
    print("\n==============================================")
    print("SIGNAL OPTIMIZER - STANDALONE TEST")
    print("==============================================")

    optimizer = SignalOptimizer()

    approaches = [
        ApproachState(
            approach_id="L1",
            traffic_pressure=80,
            queue_length=14,
            average_waiting_time=35,
            arrival_rate=22,
            starvation_time=20,
        ),
        ApproachState(
            approach_id="L2",
            traffic_pressure=45,
            queue_length=7,
            average_waiting_time=20,
            arrival_rate=14,
            starvation_time=10,
        ),
        ApproachState(
            approach_id="L3",
            traffic_pressure=25,
            queue_length=3,
            average_waiting_time=12,
            arrival_rate=8,
            starvation_time=65,
        ),
        ApproachState(
            approach_id="L4",
            traffic_pressure=60,
            queue_length=10,
            average_waiting_time=28,
            arrival_rate=18,
            starvation_time=30,
        ),
    ]

    print("\nINPUT APPROACHES")
    print("----------------------------------------------")

    for approach in approaches:
        print(
            f"{approach.approach_id}: "
            f"pressure={approach.traffic_pressure}, "
            f"queue={approach.queue_length}, "
            f"wait={approach.average_waiting_time:.1f}s, "
            f"arrival={approach.arrival_rate:.1f}/min, "
            f"starvation={approach.starvation_time:.1f}s"
        )

    decisions = optimizer.optimize(approaches)

    print("\nOPTIMIZED SIGNAL PLAN")
    print("----------------------------------------------")

    for decision in decisions:
        print(
            f"{decision.approach_id}: "
            f"priority={decision.priority_score:.2f}/100, "
            f"green={decision.green_time}s"
        )
        print(f"  Reason: {decision.reason}")

    print("\nSAFE PHASE TRANSITION")
    print("----------------------------------------------")

    transition = optimizer.get_safe_transition(
        current_approach="L1",
        next_approach=decisions[0].approach_id,
    )

    for phase in transition:
        print(f"  {phase}")

    print("\nEMERGENCY TEST")
    print("----------------------------------------------")

    emergency_approaches = [
        ApproachState(
            approach_id="L1",
            traffic_pressure=70,
            queue_length=10,
            average_waiting_time=30,
            arrival_rate=20,
        ),
        ApproachState(
            approach_id="L2",
            traffic_pressure=40,
            queue_length=5,
            average_waiting_time=15,
            arrival_rate=10,
            emergency_priority=True,
        ),
        ApproachState(
            approach_id="L3",
            traffic_pressure=50,
            queue_length=8,
            average_waiting_time=20,
            arrival_rate=15,
        ),
        ApproachState(
            approach_id="L4",
            traffic_pressure=35,
            queue_length=4,
            average_waiting_time=10,
            arrival_rate=8,
        ),
    ]

    emergency_decisions = optimizer.optimize(
        emergency_approaches
    )

    for decision in emergency_decisions:
        print(
            f"{decision.approach_id}: "
            f"green={decision.green_time}s | "
            f"{decision.reason}"
        )

    print("\n==============================================")
    print("SIGNAL OPTIMIZER TEST COMPLETE")
    print("==============================================")


if __name__ == "__main__":
    run_standalone_test()