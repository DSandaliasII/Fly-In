"""Zone model representing a single node in the drone routing network."""

from __future__ import annotations

from enum import Enum


class ZoneType(Enum):
    """The type of a zone, which determines movement cost and accessibility.

    Attributes:
        NORMAL: Standard zone, costs 1 turn to enter.
        BLOCKED: Inaccessible zone, must never be entered.
        RESTRICTED: Costs 2 turns to enter; the move is atomic (a drone
            committed to entering a restricted zone cannot wait mid-transit).
        PRIORITY: Costs 1 turn to enter, but should be favored by
            pathfinding when multiple equally-cheap options exist.
    """

    NORMAL = "normal"
    BLOCKED = "blocked"
    RESTRICTED = "restricted"
    PRIORITY = "priority"

    @property
    def movement_cost(self) -> int:
        """Return the number of turns required to move into this zone type.

        Returns:
            The turn cost, in whole turns, of entering a zone of this type.

        Raises:
            ValueError: If called on a zone type that can never be entered.
        """
        costs = {
            ZoneType.NORMAL: 1,
            ZoneType.RESTRICTED: 2,
            ZoneType.PRIORITY: 1,
        }
        if self is ZoneType.BLOCKED:
            raise ValueError("Blocked zones cannot be entered.")
        return costs[self]


class Zone:
    """A single zone (node) in the drone routing network.

    A zone has a position, a type that determines movement cost, an optional
    color for visual feedback, and a maximum simultaneous drone capacity.

    Attributes:
        name: The unique identifier of this zone.
        x: The zone's x coordinate.
        y: The zone's y coordinate.
        zone_type: The ZoneType governing cost and accessibility.
        color: An optional color string used for visual representation.
        max_drones: The maximum number of drones this zone can hold at once.
        is_start: Whether this zone is the unique start hub.
        is_end: Whether this zone is the unique end hub.
    """

    def __init__(
        self,
        name: str,
        x: int,
        y: int,
        zone_type: ZoneType = ZoneType.NORMAL,
        color: str | None = None,
        max_drones: int = 1,
        is_start: bool = False,
        is_end: bool = False,
    ) -> None:
        """Initialize a Zone.

        Args:
            name: Unique name identifying the zone.
            x: Integer x coordinate.
            y: Integer y coordinate.
            zone_type: The type of this zone (default: NORMAL).
            color: Optional color string for display purposes.
            max_drones: Maximum drones allowed simultaneously (default: 1).
                Ignored (treated as unlimited) for start/end zones.
            is_start: True if this is the unique start hub.
            is_end: True if this is the unique end hub.
        """
        self.name = name
        self.x = x
        self.y = y
        self.zone_type = zone_type
        self.color = color
        self.max_drones = max_drones
        self.is_start = is_start
        self.is_end = is_end

        # Occupancy is tracked per simulation turn by the simulator, keyed
        # implicitly by whatever turn is "current" — the zone itself only
        # exposes capacity rules, not turn-aware state, keeping this class
        # simulation-agnostic.

    @property
    def is_blocked(self) -> bool:
        """Return True if drones must never enter this zone."""
        return self.zone_type is ZoneType.BLOCKED

    @property
    def has_unlimited_capacity(self) -> bool:
        """Return True if this zone has no effective occupancy limit.

        Start and end zones are exempt from normal occupancy rules: all
        drones may share the start initially, and arriving drones at the
        end zone are considered delivered rather than occupying space.
        """
        return self.is_start or self.is_end

    @property
    def movement_cost(self) -> int:
        """Return the turn cost of moving into this zone.

        Returns:
            The number of turns required to enter this zone.
        """
        return self.zone_type.movement_cost

    def can_accept(self, current_occupancy: int) -> bool:
        """Check whether this zone can accept one more drone.

        Args:
            current_occupancy: The number of drones currently in this zone
                (for the turn being evaluated), before this move.

        Returns:
            True if the zone can accept another drone given its capacity
            rules, False otherwise.
        """
        if self.is_blocked:
            return False
        if self.has_unlimited_capacity:
            return True
        return current_occupancy < self.max_drones

    def __repr__(self) -> str:
        """Return a debug-friendly representation of this zone."""
        return (
            f"Zone(name={self.name!r}, x={self.x}, y={self.y}, "
            f"type={self.zone_type.value}, max_drones={self.max_drones})"
        )

    def __eq__(self, other: object) -> bool:
        """Compare zones by name, since names are unique identifiers."""
        if not isinstance(other, Zone):
            return NotImplemented
        return self.name == other.name

    def __hash__(self) -> int:
        """Hash zones by name so they can be used in sets/dict keys."""
        return hash(self.name)
