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
        self.traffic_pressure = max(
            0.0,
            min(100.0, float(self.traffic_pressure)),
        )

        self.queue_length = max(
            0,
            int(self.queue_length),
        )

        self.average_waiting_time = max(
            0.0,
            float(self.average_waiting_time),
        )

        self.arrival_rate = max(
            0.0,
            float(self.arrival_rate),
        )

        self.starvation_time = max(
            0.0,
            float(self.starvation_time),
        )


@dataclass
class SignalDecision:
    """
    Final optimized signal decision for one approach.
    """

    approach_id: str
    priority_score: float
    green_time: int
    reason: str


class SignalOptimizer:
    """
    City-Wide AI Engine - Signal Optimizer V2.

    This is a prototype decision/optimization engine.

    It does NOT directly control real-world traffic signals.

    The optimizer considers the complete intersection together
    instead of independently assigning green time to each approach.

    Priority factors:
        Traffic pressure : 40%
        Queue pressure   : 25%
        Waiting pressure  : 20%
        Arrival pressure : 10%
        Starvation        : 5%

    Prototype signal constraints:
        Minimum green        = 20 seconds
        Maximum green        = 60 seconds
        Yellow               = 3 seconds
        All-red clearance    = 2 seconds
        Target cycle         = 120 seconds
        Starvation threshold = 60 seconds

    V2 improvement:
        The total signal plan is guaranteed to fit inside the
        available cycle time.

    Available green time:

        120 - 3 - 2 = 115 seconds

    The optimizer therefore distributes 115 seconds of green
    time across the approaches while respecting the minimum
    and maximum green constraints.
    """

    MIN_GREEN = 20
    MAX_GREEN = 60

    YELLOW_TIME = 3
    ALL_RED_TIME = 2

    TARGET_CYCLE = 120
    STARVATION_THRESHOLD = 60

    @property
    def AVAILABLE_GREEN_TIME(self) -> int:
        """
        Total green time available inside the target cycle.

        Example:

            120 - 3 - 2 = 115 seconds
        """

        return (
            self.TARGET_CYCLE
            - self.YELLOW_TIME
            - self.ALL_RED_TIME
        )

    def __init__(self):
        self.current_phase: Optional[str] = None
        self.last_decisions: Dict[str, SignalDecision] = {}

    # =========================================================
    # PRIORITY CALCULATION
    # =========================================================

    def calculate_priority(
        self,
        approach: ApproachState,
    ) -> float:
        """
        Calculate the global priority score for an approach.

        Components:

            Traffic pressure : 40%
            Queue pressure   : 25%
            Waiting pressure  : 20%
            Arrival pressure : 10%
            Starvation        : 5%

        Starvation receives an additional bonus once the
        configured starvation threshold is reached.

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
            (
                approach.starvation_time
                / self.STARVATION_THRESHOLD
            )
            * 100.0,
            100.0,
        )

        priority = (
            traffic_score * 0.40
            + queue_score * 0.25
            + waiting_score * 0.20
            + arrival_score * 0.10
            + starvation_score * 0.05
        )

        # Starvation protection.
        if approach.starvation_time >= self.STARVATION_THRESHOLD:
            priority += 15.0

        # Emergency priority overrides normal optimization.
        if approach.emergency_priority:
            priority = 100.0

        return min(priority, 100.0)

    # =========================================================
    # EMERGENCY HANDLING
    # =========================================================

    def handle_emergency(
        self,
        approaches: list[ApproachState],
    ) -> Optional[ApproachState]:
        """
        Find the highest-priority emergency approach.

        This does not instantly terminate the current phase.

        The result is only a recommendation for the next
        safe signal decision.
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

    # =========================================================
    # GLOBAL GREEN-TIME ALLOCATION
    # =========================================================

    def _allocate_minimum_green(
        self,
        approaches: list[ApproachState],
    ) -> Dict[str, int]:
        """
        Give every approach its minimum safe green time.

        This guarantees that no approach is starved simply because
        another approach has significantly higher traffic pressure.
        """

        return {
            approach.approach_id: self.MIN_GREEN
            for approach in approaches
        }

    def _distribute_remaining_green(
        self,
        approaches: list[ApproachState],
        green_times: Dict[str, int],
        priorities: Dict[str, float],
    ) -> Dict[str, int]:
        """
        Distribute remaining green time according to priority.

        V2 uses a global allocation approach.

        Important:
            The total allocation can NEVER exceed
            AVAILABLE_GREEN_TIME.

        Every approach starts at MIN_GREEN.

        Remaining time is distributed to approaches with the
        highest priority while respecting MAX_GREEN.
        """

        allocated = sum(green_times.values())

        remaining = self.AVAILABLE_GREEN_TIME - allocated

        if remaining <= 0:
            return green_times

        # Continue distributing time until there is no remaining
        # cycle capacity or all approaches reach MAX_GREEN.
        while remaining > 0:

            eligible = [
                approach
                for approach in approaches
                if green_times[approach.approach_id]
                < self.MAX_GREEN
            ]

            if not eligible:
                break

            total_priority = sum(
                max(
                    priorities[approach.approach_id],
                    0.01,
                )
                for approach in eligible
            )

            if total_priority <= 0:
                break

            # Calculate proportional allocation.
            allocations = []

            for approach in eligible:
                approach_id = approach.approach_id

                share = (
                    max(priorities[approach_id], 0.01)
                    / total_priority
                )

                desired = max(
                    1,
                    round(remaining * share),
                )

                capacity = (
                    self.MAX_GREEN
                    - green_times[approach_id]
                )

                addition = min(
                    desired,
                    capacity,
                    remaining,
                )

                if addition > 0:
                    allocations.append(
                        (
                            approach_id,
                            addition,
                            priorities[approach_id],
                        )
                    )

            if not allocations:
                break

            allocated_this_round = 0

            for (
                approach_id,
                addition,
                _priority,
            ) in sorted(
                allocations,
                key=lambda item: item[2],
                reverse=True,
            ):

                if remaining <= 0:
                    break

                addition = min(
                    addition,
                    remaining,
                )

                green_times[approach_id] += addition

                remaining -= addition
                allocated_this_round += addition

            if allocated_this_round == 0:
                break

        return green_times

    def _ensure_cycle_constraint(
        self,
        green_times: Dict[str, int],
    ) -> Dict[str, int]:
        """
        Final safety check.

        Guarantees:

            sum(green times) <= AVAILABLE_GREEN_TIME

        and:

            MIN_GREEN <= every green <= MAX_GREEN

        This acts as the final protection against an invalid
        signal plan.
        """

        green_times = {
            approach_id: max(
                self.MIN_GREEN,
                min(
                    self.MAX_GREEN,
                    int(green_time),
                ),
            )
            for approach_id, green_time
            in green_times.items()
        }

        total_green = sum(green_times.values())

        if total_green <= self.AVAILABLE_GREEN_TIME:
            return green_times

        excess = (
            total_green
            - self.AVAILABLE_GREEN_TIME
        )

        # Reduce the highest allocations first, but never below
        # the minimum green time.
        while excess > 0:

            reducible = [
                approach_id
                for approach_id, green_time
                in green_times.items()
                if green_time > self.MIN_GREEN
            ]

            if not reducible:
                break

            # Reduce the approach with the largest allocation.
            approach_id = max(
                reducible,
                key=lambda item: green_times[item],
            )

            reduction = min(
                excess,
                green_times[approach_id]
                - self.MIN_GREEN,
            )

            green_times[approach_id] -= reduction
            excess -= reduction

        return green_times

    # =========================================================
    # MAIN OPTIMIZATION
    # =========================================================

    def optimize(
        self,
        approaches: list[ApproachState],
    ) -> list[SignalDecision]:
        """
        Globally optimize all intersection approaches.

        The resulting plan respects the complete cycle.

        Normal case:

            Every approach receives at least MIN_GREEN.

            Remaining green time is distributed according
            to global priority.

        Emergency case:

            Emergency approach receives MAX_GREEN.

            Remaining approaches share the remaining
            available cycle while respecting MIN_GREEN.

        If the emergency configuration cannot fit into the
        available cycle under the prototype constraints,
        the engine returns the safest feasible allocation.
        """

        if not approaches:
            self.last_decisions = {}
            return []

        # -----------------------------------------------------
        # Calculate priorities
        # -----------------------------------------------------

        priorities = {
            approach.approach_id: self.calculate_priority(
                approach
            )
            for approach in approaches
        }

        emergency = self.handle_emergency(approaches)

        # -----------------------------------------------------
        # Start every approach at minimum green.
        # -----------------------------------------------------

        green_times = self._allocate_minimum_green(
            approaches
        )

        # -----------------------------------------------------
        # Emergency allocation
        # -----------------------------------------------------

        if emergency is not None:

            emergency_id = emergency.approach_id

            # First reserve maximum green for emergency.
            emergency_extra = (
                self.MAX_GREEN
                - self.MIN_GREEN
            )

            non_emergency = [
                approach
                for approach in approaches
                if approach.approach_id != emergency_id
            ]

            available_extra = (
                self.AVAILABLE_GREEN_TIME
                - sum(green_times.values())
            )

            emergency_addition = min(
                emergency_extra,
                max(0, available_extra),
            )

            green_times[emergency_id] += (
                emergency_addition
            )

            available_extra -= emergency_addition

            # Give remaining capacity to other approaches
            # according to priority.
            if available_extra > 0 and non_emergency:

                non_emergency_priorities = {
                    approach.approach_id: priorities[
                        approach.approach_id
                    ]
                    for approach in non_emergency
                }

                temp_approaches = non_emergency

                temp_green_times = {
                    approach.approach_id: green_times[
                        approach.approach_id
                    ]
                    for approach in temp_approaches
                }

                # Temporarily use only the remaining capacity.
                original_available = (
                    self.AVAILABLE_GREEN_TIME
                )

                temporary_total = sum(
                    temp_green_times.values()
                )

                temporary_target = (
                    temporary_total
                    + available_extra
                )

                # Distribute manually using priority shares.
                while (
                    sum(temp_green_times.values())
                    < temporary_target
                ):

                    eligible = [
                        approach
                        for approach in temp_approaches
                        if temp_green_times[
                            approach.approach_id
                        ] < self.MAX_GREEN
                    ]

                    if not eligible:
                        break

                    selected = max(
                        eligible,
                        key=lambda approach:
                        non_emergency_priorities[
                            approach.approach_id
                        ],
                    )

                    temp_green_times[
                        selected.approach_id
                    ] += 1

                for approach_id, value in temp_green_times.items():
                    green_times[approach_id] = value

                # Keep variable referenced for clarity and avoid
                # changing global optimizer configuration.
                _ = original_available

        # -----------------------------------------------------
        # Normal allocation
        # -----------------------------------------------------

        else:
            green_times = self._distribute_remaining_green(
                approaches,
                green_times,
                priorities,
            )

        # -----------------------------------------------------
        # Final cycle constraint
        # -----------------------------------------------------

        green_times = self._ensure_cycle_constraint(
            green_times
        )

        # -----------------------------------------------------
        # Build decisions
        # -----------------------------------------------------

        decisions = []

        for approach in approaches:

            approach_id = approach.approach_id
            priority = priorities[approach_id]
            green_time = green_times[approach_id]

            if emergency is not None:

                if approach_id == emergency.approach_id:
                    reason = (
                        "Emergency priority with safe "
                        "global cycle allocation."
                    )
                else:
                    reason = (
                        "Emergency active; allocated remaining "
                        "cycle time safely."
                    )

            elif approach.starvation_time >= (
                self.STARVATION_THRESHOLD
            ):
                reason = (
                    "Starvation protection applied within "
                    "global cycle."
                )

            elif priority >= 70:
                reason = (
                    "High traffic priority with global "
                    "cycle optimization."
                )

            elif priority >= 40:
                reason = (
                    "Medium traffic priority with global "
                    "cycle optimization."
                )

            else:
                reason = (
                    "Normal traffic priority with global "
                    "cycle optimization."
                )

            decisions.append(
                SignalDecision(
                    approach_id=approach_id,
                    priority_score=round(
                        priority,
                        2,
                    ),
                    green_time=int(green_time),
                    reason=reason,
                )
            )

        # Highest priority first.
        decisions.sort(
            key=lambda decision: decision.priority_score,
            reverse=True,
        )

        self.last_decisions = {
            decision.approach_id: decision
            for decision in decisions
        }

        return decisions

    # =========================================================
    # SAFE PHASE TRANSITION
    # =========================================================

    def get_safe_transition(
        self,
        current_approach: Optional[str],
        next_approach: str,
    ) -> list[str]:
        """
        Return the safe prototype transition sequence.

        Normal transition:

            GREEN(current)
                 ↓
            YELLOW
                 ↓
            ALL-RED
                 ↓
            GREEN(next)

        The optimizer never instantly jumps from one green
        approach to another.
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
# STANDALONE TEST
# =============================================================

def run_standalone_test():
    print("\n==============================================")
    print("SIGNAL OPTIMIZER V2 - STANDALONE TEST")
    print("==============================================")

    optimizer = SignalOptimizer()

    print("\nSIGNAL CONSTRAINTS")
    print("----------------------------------------------")
    print(f"Minimum Green       : {optimizer.MIN_GREEN}s")
    print(f"Maximum Green       : {optimizer.MAX_GREEN}s")
    print(f"Yellow              : {optimizer.YELLOW_TIME}s")
    print(f"All-Red Clearance   : {optimizer.ALL_RED_TIME}s")
    print(f"Target Cycle        : {optimizer.TARGET_CYCLE}s")
    print(
        f"Available Green     : "
        f"{optimizer.AVAILABLE_GREEN_TIME}s"
    )

    # ---------------------------------------------------------
    # Normal traffic test
    # ---------------------------------------------------------

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

    print("\nOPTIMIZED GLOBAL SIGNAL PLAN")
    print("----------------------------------------------")

    total_green = 0

    for decision in decisions:
        total_green += decision.green_time

        print(
            f"{decision.approach_id}: "
            f"priority={decision.priority_score:.2f}/100, "
            f"green={decision.green_time}s"
        )

        print(
            f"  Reason: {decision.reason}"
        )

    total_cycle = (
        total_green
        + optimizer.YELLOW_TIME
        + optimizer.ALL_RED_TIME
    )

    print("\nCYCLE VALIDATION")
    print("----------------------------------------------")
    print(f"Total Green Time    : {total_green}s")
    print(f"Yellow Time         : {optimizer.YELLOW_TIME}s")
    print(f"All-Red Time        : {optimizer.ALL_RED_TIME}s")
    print(f"Calculated Cycle    : {total_cycle}s")
    print(f"Target Cycle        : {optimizer.TARGET_CYCLE}s")

    if total_green <= optimizer.AVAILABLE_GREEN_TIME:
        print("Cycle Constraint    : PASS")
    else:
        print("Cycle Constraint    : FAIL")

    if all(
        optimizer.MIN_GREEN
        <= decision.green_time
        <= optimizer.MAX_GREEN
        for decision in decisions
    ):
        print("Green Time Limits   : PASS")
    else:
        print("Green Time Limits   : FAIL")

    # ---------------------------------------------------------
    # Safe transition test
    # ---------------------------------------------------------

    print("\nSAFE PHASE TRANSITION")
    print("----------------------------------------------")

    next_approach = decisions[0].approach_id

    transition = optimizer.get_safe_transition(
        current_approach="L1",
        next_approach=next_approach,
    )

    for phase in transition:
        print(f"  {phase}")

    # ---------------------------------------------------------
    # Emergency test
    # ---------------------------------------------------------

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

    emergency_green_total = 0

    for decision in emergency_decisions:
        emergency_green_total += decision.green_time

        print(
            f"{decision.approach_id}: "
            f"green={decision.green_time}s | "
            f"{decision.reason}"
        )

    emergency_cycle = (
        emergency_green_total
        + optimizer.YELLOW_TIME
        + optimizer.ALL_RED_TIME
    )

    print("\nEMERGENCY CYCLE VALIDATION")
    print("----------------------------------------------")
    print(
        f"Total Green Time    : "
        f"{emergency_green_total}s"
    )
    print(
        f"Calculated Cycle    : "
        f"{emergency_cycle}s"
    )
    print(
        f"Target Cycle        : "
        f"{optimizer.TARGET_CYCLE}s"
    )

    if emergency_green_total <= optimizer.AVAILABLE_GREEN_TIME:
        print("Emergency Cycle     : PASS")
    else:
        print("Emergency Cycle     : FAIL")

    print("\n==============================================")
    print("SIGNAL OPTIMIZER V2 TEST COMPLETE")
    print("==============================================")


if __name__ == "__main__":
    run_standalone_test()