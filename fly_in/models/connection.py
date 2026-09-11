"""Connection model representing a bidirectional edge between two zones."""

from __future__ import annotations

from models.zone import Zone


class Connection:
    """A bidirectional connection (edge) between two zones.

    Attributes:
        zone_a: One endpoint of the connection.
        zone_b: The other endpoint of the connection.
        max_link_capacity: The maximum number of drones that may traverse
            this connection simultaneously.
    """

    def __init__(
        self,
        zone_a: Zone,
        zone_b: Zone,
        max_link_capacity: int = 1,
    ) -> None:
        """Initialize a Connection between two zones.

        Args:
            zone_a: One endpoint zone.
            zone_b: The other endpoint zone.
            max_link_capacity: Maximum simultaneous traversals allowed
                (default: 1).
        """
        self.zone_a = zone_a
        self.zone_b = zone_b
        self.max_link_capacity = max_link_capacity

    @property
    def name(self) -> str:
        """Return a canonical, order-independent name for this connection.

        Used both for display (e.g. "D1-corridorA-tunnelB" style output for
        in-flight restricted moves) and as a dictionary key for capacity
        tracking, so the same connection is recognized regardless of which
        endpoint is treated as "first". Dashes are safe as a separator here
        because zone names are forbidden from containing them, matching the
        "connection: <zone1>-<zone2>" syntax used in map files.
        """
        first, second = sorted((self.zone_a.name, self.zone_b.name))
        return f"{first}-{second}"

    def other_end(self, zone: Zone) -> Zone:
        """Return the endpoint of this connection opposite the given zone.

        Args:
            zone: One of the two endpoint zones.

        Returns:
            The other endpoint zone.

        Raises:
            ValueError: If the given zone is not an endpoint of this
                connection.
        """
        if zone == self.zone_a:
            return self.zone_b
        if zone == self.zone_b:
            return self.zone_a
        raise ValueError(
            f"Zone {zone.name!r} is not an endpoint of connection "
            f"{self.name!r}."
        )

    def connects(self, zone_a: Zone, zone_b: Zone) -> bool:
        """Check whether this connection links the two given zones.

        Args:
            zone_a: A candidate endpoint.
            zone_b: The other candidate endpoint.

        Returns:
            True if this connection links exactly these two zones,
            regardless of order.
        """
        pair = {zone_a.name, zone_b.name}
        return pair == {self.zone_a.name, self.zone_b.name}

    def can_accept(self, current_traversals: int) -> bool:
        """Check whether this connection can accept one more traversal.

        Args:
            current_traversals: The number of drones currently traversing
                this connection for the turn being evaluated.

        Returns:
            True if the connection has spare capacity, False otherwise.
        """
        return current_traversals < self.max_link_capacity

    def __repr__(self) -> str:
        """Return a debug-friendly representation of this connection."""
        return (
            f"Connection({self.zone_a.name!r}-{self.zone_b.name!r}, "
            f"max_link_capacity={self.max_link_capacity})"
        )

    def __eq__(self, other: object) -> bool:
        """Compare connections by their canonical endpoint pair."""
        if not isinstance(other, Connection):
            return NotImplemented
        return self.connects(other.zone_a, other.zone_b)

    def __hash__(self) -> int:
        """Hash connections by their canonical name."""
        return hash(self.name)
