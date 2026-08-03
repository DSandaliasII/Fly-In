"""Network model: a hand-built graph of zones and connections.

No external graph libraries (networkx, graphlib, etc.) are used anywhere in
this module, per the project constraints — adjacency is tracked with plain
dictionaries and lists.
"""

from __future__ import annotations

from exceptions import InvalidConnectionError, ZoneNotFoundError
from models.connection import Connection
from models.zone import Zone


class Network:
    """A graph of Zones connected by Connections.

    Attributes:
        zones: Mapping of zone name to Zone instance.
        connections: List of all Connection instances in the network.
        start_zone: The unique start hub.
        end_zone: The unique end hub.
    """

    def __init__(self) -> None:
        """Initialize an empty Network."""
        self.zones: dict[str, Zone] = {}
        self.connections: list[Connection] = []
        self._adjacency: dict[str, list[Connection]] = {}
        self.start_zone: Zone | None = None
        self.end_zone: Zone | None = None

    def add_zone(self, zone: Zone) -> None:
        """Add a zone to the network.

        Args:
            zone: The Zone to add.

        Raises:
            InvalidConnectionError: If a zone with the same name already
                exists, or if this would introduce a second start/end zone.
        """
        if zone.name in self.zones:
            raise InvalidConnectionError(
                f"Duplicate zone name: {zone.name!r}."
            )
        if zone.is_start:
            if self.start_zone is not None:
                raise InvalidConnectionError(
                    "A start zone is already defined "
                    f"({self.start_zone.name!r})."
                )
            self.start_zone = zone
        if zone.is_end:
            if self.end_zone is not None:
                raise InvalidConnectionError(
                    "An end zone is already defined "
                    f"({self.end_zone.name!r})."
                )
            self.end_zone = zone

        self.zones[zone.name] = zone
        self._adjacency[zone.name] = []

    def get_zone(self, name: str) -> Zone:
        """Look up a zone by name.

        Args:
            name: The zone name to look up.

        Returns:
            The matching Zone.

        Raises:
            ZoneNotFoundError: If no zone with that name exists.
        """
        try:
            return self.zones[name]
        except KeyError as exc:
            raise ZoneNotFoundError(
                f"No zone named {name!r} in the network."
            ) from exc

    def add_connection(self, connection: Connection) -> None:
        """Add a connection to the network.

        Args:
            connection: The Connection to add. Both endpoints must already
                be registered zones.

        Raises:
            ZoneNotFoundError: If either endpoint is not a known zone.
            InvalidConnectionError: If an equivalent connection (same pair
                of endpoints, regardless of order) already exists.
        """
        for endpoint in (connection.zone_a, connection.zone_b):
            if endpoint.name not in self.zones:
                raise ZoneNotFoundError(
                    f"Connection references unknown zone {endpoint.name!r}."
                )

        if any(existing == connection for existing in self.connections):
            raise InvalidConnectionError(
                f"Duplicate connection: {connection.name!r} already exists."
            )

        self.connections.append(connection)
        self._adjacency[connection.zone_a.name].append(connection)
        self._adjacency[connection.zone_b.name].append(connection)

    def neighbors(self, zone: Zone) -> list[tuple[Zone, Connection]]:
        """List the reachable neighbors of a zone.

        Args:
            zone: The zone to query neighbors for.

        Returns:
            A list of (neighbor_zone, connection) pairs. Neighbors whose
            zone type is BLOCKED are excluded, since drones must never
            enter them.
        """
        result: list[tuple[Zone, Connection]] = []
        for connection in self._adjacency.get(zone.name, []):
            neighbor = connection.other_end(zone)
            if neighbor.is_blocked:
                continue
            result.append((neighbor, connection))
        return result

    def get_connection(self, zone_a: Zone, zone_b: Zone) -> Connection:
        """Retrieve the connection directly linking two zones.

        Args:
            zone_a: One endpoint.
            zone_b: The other endpoint.

        Returns:
            The Connection linking the two zones.

        Raises:
            ZoneNotFoundError: If no direct connection exists between them.
        """
        for connection in self._adjacency.get(zone_a.name, []):
            if connection.connects(zone_a, zone_b):
                return connection
        raise ZoneNotFoundError(
            f"No direct connection between {zone_a.name!r} and "
            f"{zone_b.name!r}."
        )

    def validate(self) -> None:
        """Validate overall network integrity.

        Raises:
            InvalidConnectionError: If no start zone or no end zone has
                been defined.
        """
        if self.start_zone is None:
            raise InvalidConnectionError("Network has no start zone.")
        if self.end_zone is None:
            raise InvalidConnectionError("Network has no end zone.")

    def __len__(self) -> int:
        """Return the number of zones in the network."""
        return len(self.zones)

    def __repr__(self) -> str:
        """Return a debug-friendly representation of this network."""
        return (
            f"Network(zones={len(self.zones)}, "
            f"connections={len(self.connections)})"
        )
