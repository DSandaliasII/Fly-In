"""Drone model representing a single agent moving through the network."""

from __future__ import annotations

from enum import Enum, auto

from models.connection import Connection
from models.zone import Zone


class DroneState(Enum):
    """The current movement state of a drone.

    Attributes:
        WAITING: The drone is holding its current zone this turn.
        AT_ZONE: The drone occupies a zone and is not mid-transit.
        IN_TRANSIT: The drone is mid-transit on a restricted-zone
            connection and is committed to arriving next turn.
        DELIVERED: The drone has reached the end zone and is no longer
            tracked by the simulation.
    """

    AT_ZONE = auto()
    WAITING = auto()
    IN_TRANSIT = auto()
    DELIVERED = auto()


class Drone:
    """A single drone navigating from the start zone to the end zone.

    The Drone class only tracks the agent's own state (position, path,
    transit status). It has no knowledge of other drones or of capacity
    rules — that coordination is the responsibility of the scheduler.

    Attributes:
        drone_id: The unique identifier of this drone (e.g. "D1").
        current_zone: The zone this drone currently occupies, or the zone
            it departed from if currently in transit.
        path: The full sequence of zones this drone intends to traverse,
            from start to end, as computed by the pathfinder.
        path_index: The index into `path` of the drone's current or most
            recently departed zone.
        state: The drone's current DroneState.
        in_transit_connection: The Connection currently being traversed, if
            the drone is IN_TRANSIT; otherwise None.
        transit_turns_remaining: The number of turns left before the drone
            arrives at its destination, if IN_TRANSIT; otherwise None.
        turns_taken: The total number of turns this drone has spent so far,
            used for optional secondary scoring metrics.
    """

    def __init__(self, drone_id: str, start_zone: Zone) -> None:
        """Initialize a Drone at the given start zone.

        Args:
            drone_id: Unique identifier for this drone (e.g. "D1").
            start_zone: The zone the drone begins at.
        """
        self.drone_id = drone_id
        self.current_zone = start_zone
        self.path: list[Zone] = [start_zone]
        self.path_index = 0
        self.state = DroneState.AT_ZONE
        self.in_transit_connection: Connection | None = None
        self.transit_turns_remaining: int | None = None
        self.turns_taken = 0
        self._pending_destination: Zone | None = None

    def assign_path(self, path: list[Zone]) -> None:
        """Assign or replace this drone's planned route.

        Args:
            path: An ordered list of zones from the drone's current zone
                to the end zone (inclusive of both endpoints).

        Raises:
            ValueError: If the path is empty or does not start at the
                drone's current zone.
        """
        if not path:
            raise ValueError("Assigned path must not be empty.")
        if path[0] != self.current_zone:
            raise ValueError(
                "Assigned path must start at the drone's current zone "
                f"({self.current_zone.name!r}), got {path[0].name!r}."
            )
        self.path = path
        self.path_index = 0

    @property
    def next_zone(self) -> Zone | None:
        """Return the next zone in this drone's path, if any.

        Returns:
            The next Zone the drone intends to move to, or None if the
            drone has no further planned moves (e.g. already delivered).
        """
        next_index = self.path_index + 1
        if next_index >= len(self.path):
            return None
        return self.path[next_index]

    @property
    def is_delivered(self) -> bool:
        """Return True if this drone has reached the end zone."""
        return self.state is DroneState.DELIVERED

    def begin_transit(
        self, connection: Connection, destination: Zone, turns: int
    ) -> None:
        """Mark this drone as having committed to a multi-turn transit.

        Args:
            connection: The connection being traversed.
            destination: The zone the drone will arrive at.
            turns: The number of turns the transit will take (e.g. 2 for a
                restricted zone).

        Raises:
            ValueError: If turns is not a positive integer.
        """
        if turns <= 0:
            raise ValueError("Transit duration must be a positive integer.")
        self.state = DroneState.IN_TRANSIT
        self.in_transit_connection = connection
        self.transit_turns_remaining = turns
        self._pending_destination = destination

    def advance_transit(self) -> bool:
        """Advance an in-progress transit by one turn.

        Returns:
            True if the drone has now arrived at its destination (transit
            complete), False if it remains in transit.

        Raises:
            ValueError: If called while the drone is not in transit.
        """
        if (
            self.state is not DroneState.IN_TRANSIT
            or self.transit_turns_remaining is None
        ):
            raise ValueError("Drone is not currently in transit.")

        self.transit_turns_remaining -= 1
        if self.transit_turns_remaining <= 0:
            self._complete_transit()
            return True
        return False

    def _complete_transit(self) -> None:
        """Finalize a completed transit, moving the drone into its zone."""
        if self._pending_destination is None:
            raise ValueError(
                "Transit completed with no pending destination recorded."
            )
        destination = self._pending_destination
        self._pending_destination = None
        self.in_transit_connection = None
        self.transit_turns_remaining = None
        self.move_to(destination)

    def move_to(self, zone: Zone) -> None:
        """Move this drone directly into the given zone (single-turn move).

        Args:
            zone: The destination zone. Must be the drone's next planned
                zone in its path.

        Raises:
            ValueError: If the given zone is not the drone's next planned
                zone.
        """
        if self.next_zone != zone:
            expected = self.next_zone.name if self.next_zone else "<none>"
            raise ValueError(
                f"Drone {self.drone_id!r} cannot move to {zone.name!r}; "
                f"expected next zone {expected!r}."
            )
        self.current_zone = zone
        self.path_index += 1
        self.turns_taken += 1
        self.state = (
            DroneState.DELIVERED if zone.is_end else DroneState.AT_ZONE
        )

    def wait(self) -> None:
        """Mark this drone as waiting (staying in place) for one turn."""
        if self.state is DroneState.IN_TRANSIT:
            raise ValueError(
                f"Drone {self.drone_id!r} cannot wait while in transit."
            )
        self.state = DroneState.WAITING
        self.turns_taken += 1

    def __repr__(self) -> str:
        """Return a debug-friendly representation of this drone."""
        return (
            f"Drone(id={self.drone_id!r}, zone={self.current_zone.name!r}, "
            f"state={self.state.name})"
        )
