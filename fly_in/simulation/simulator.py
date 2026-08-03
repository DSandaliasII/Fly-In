"""Top-level simulation orchestrator.

Wires together the Network (already parsed), the Pathfinder, and the
Scheduler: it creates the drone fleet, assigns each drone an initial route,
runs the turn-by-turn simulation, and packages the result (including the
turn-by-turn output and optional secondary metrics) for display.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from models.drone import Drone
from models.network import Network
from pathfinding.pathfinder import Pathfinder
from simulation.scheduler import Scheduler


@dataclass
class SimulationResult:
    """The outcome of a full simulation run.

    Attributes:
        turn_log: The turn-by-turn movement log, as produced by the
            Scheduler; each entry is the list of movement strings for one
            turn.
        nb_drones: The number of drones that were simulated.
        total_turns: The total number of turns taken to deliver every
            drone (the primary scoring metric).
        turns_per_drone: Mapping of drone ID to the number of turns that
            drone individually spent traveling (a secondary metric).
    """

    turn_log: list[list[str]]
    nb_drones: int
    total_turns: int = field(init=False)
    turns_per_drone: dict[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Derive total_turns from the length of the turn log."""
        self.total_turns = len(self.turn_log)

    @property
    def average_turns_per_drone(self) -> float:
        """Return the average number of turns spent per drone.

        Returns:
            The mean of turns_per_drone values, or 0.0 if there is no
            data (e.g. zero drones).
        """
        if not self.turns_per_drone:
            return 0.0
        return sum(self.turns_per_drone.values()) / len(self.turns_per_drone)

    def format_output(self) -> str:
        """Format the turn log per the required simulation output format.

        Returns:
            One line per turn, with space-separated "D<id>-<destination>"
            movement entries, matching the format specified for the
            simulation output.
        """
        return "\n".join(" ".join(turn) for turn in self.turn_log)


class Simulator:
    """Orchestrates a full drone-routing simulation for a parsed map.

    Attributes:
        network: The Network to simulate over.
        nb_drones: The number of drones to route from start to end.
    """

    def __init__(self, network: Network, nb_drones: int) -> None:
        """Initialize the Simulator.

        Args:
            network: A validated Network (start/end zones present).
            nb_drones: The number of drones to create and route.
        """
        self.network = network
        self.nb_drones = nb_drones

    def run(self) -> SimulationResult:
        """Run the full simulation: route planning followed by scheduling.

        Returns:
            A SimulationResult describing the outcome.

        Raises:
            NoPathFoundError: If no route exists between the start and end
                zones for the initial path assignment.
            DeadlockError: If the scheduler cannot make progress.
        """
        drones = self._create_drones()
        self._assign_initial_paths(drones)

        scheduler = Scheduler(self.network, drones)
        turn_log = scheduler.run()

        return SimulationResult(
            turn_log=turn_log,
            nb_drones=self.nb_drones,
            turns_per_drone={
                drone.drone_id: drone.turns_taken for drone in drones
            },
        )

    def _create_drones(self) -> list[Drone]:
        """Create the drone fleet, all starting at the network's start zone.

        Returns:
            A list of newly created Drone instances, named "D1".."Dn".

        Raises:
            ValueError: If the network has no start zone defined (should
                never happen for a validated Network).
        """
        if self.network.start_zone is None:
            raise ValueError("Network has no start zone defined.")

        start = self.network.start_zone
        return [
            Drone(drone_id=f"D{i}", start_zone=start)
            for i in range(1, self.nb_drones + 1)
        ]

    def _assign_initial_paths(self, drones: list[Drone]) -> None:
        """Compute and assign the initial shortest path for every drone.

        Args:
            drones: The drones to assign paths to.

        Raises:
            ValueError: If the network has no end zone defined (should
                never happen for a validated Network).
        """
        if self.network.end_zone is None:
            raise ValueError("Network has no end zone defined.")

        end = self.network.end_zone
        pathfinder = Pathfinder(self.network)

        for drone in drones:
            result = pathfinder.shortest_path(drone.current_zone, end)
            drone.assign_path(result.zones)
