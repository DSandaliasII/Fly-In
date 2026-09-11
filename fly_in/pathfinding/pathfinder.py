"""Custom shortest-path pathfinding over a Network.

Implements Dijkstra's algorithm by hand using Python's built-in heapq as a
priority queue. No external graph libraries are used, per the project
constraints. Movement cost is determined by the destination zone's type
(normal/priority = 1 turn, restricted = 2 turns, blocked = impassable).
"""

from __future__ import annotations

import heapq
from dataclasses import dataclass, field

from exceptions import NoPathFoundError
from models.network import Network
from models.zone import Zone, ZoneType

# Small tie-breaking bonus favoring priority zones when two candidate paths
# have identical raw turn cost. This never changes which path is cheapest
# in terms of turns; it only nudges ties toward priority zones, honoring
# the "should be prioritized in pathfinding" rule without corrupting the
# actual turn-cost accounting used for scoring.
_PRIORITY_TIE_BREAK_BONUS = 0.001


@dataclass(order=True)
class _QueueEntry:
    """An entry in the Dijkstra priority queue.

    Attributes:
        priority: The effective (cost, tie-break) value used for ordering.
        zone: The zone this entry refers to (excluded from comparison).
    """

    priority: float
    zone: Zone = field(compare=False)


@dataclass
class PathResult:
    """The result of a successful pathfinding query.

    Attributes:
        zones: The ordered list of zones from start to end, inclusive.
        total_turns: The total number of turns required to traverse this
            path, accounting for zone movement costs.
    """

    zones: list[Zone]
    total_turns: int


class Pathfinder:
    """Computes shortest weighted paths between zones in a Network.

    The Pathfinder is stateless with respect to other drones — it computes
    the cheapest possible route for a single drone in isolation. Multi-drone
    coordination (avoiding capacity conflicts) is handled separately by the
    simulation scheduler, which may request alternate paths from this class
    when the default shortest path is contended.
    """

    def __init__(self, network: Network) -> None:
        """Initialize the Pathfinder for a given network.

        Args:
            network: The Network to compute paths over.
        """
        self.network = network

    def shortest_path(
        self,
        start: Zone,
        end: Zone,
        excluded_zones: frozenset[str] = frozenset(),
    ) -> PathResult:
        """Compute the cheapest path from start to end via Dijkstra.

        Args:
            start: The zone to start from.
            end: The target zone.
            excluded_zones: Names of zones to treat as unusable for this
                query (e.g. to force an alternate route around congestion).
                The start and end zones are never excluded even if listed.

        Returns:
            A PathResult describing the cheapest route found.

        Raises:
            NoPathFoundError: If no valid route exists from start to end.
        """
        distances: dict[str, float] = {start.name: 0.0}
        turn_costs: dict[str, int] = {start.name: 0}
        previous: dict[str, Zone] = {}
        visited: set[str] = set()

        queue: list[_QueueEntry] = [_QueueEntry(0.0, start)]

        while queue:
            current_entry = heapq.heappop(queue)
            current = current_entry.zone

            if current.name in visited:
                continue
            visited.add(current.name)

            if current.name == end.name:
                break

            for neighbor, _connection in self.network.neighbors(current):
                if neighbor.name in visited:
                    continue
                if (
                    neighbor.name in excluded_zones
                    and neighbor.name != end.name
                ):
                    continue

                step_cost = neighbor.movement_cost
                tie_break = (
                    -_PRIORITY_TIE_BREAK_BONUS
                    if neighbor.zone_type is ZoneType.PRIORITY
                    else 0.0
                )
                candidate = (
                    distances[current.name] + step_cost + tie_break
                )
                candidate_turns = turn_costs[current.name] + step_cost

                if candidate < distances.get(neighbor.name, float("inf")):
                    distances[neighbor.name] = candidate
                    turn_costs[neighbor.name] = candidate_turns
                    previous[neighbor.name] = current
                    heapq.heappush(queue, _QueueEntry(candidate, neighbor))

        if end.name not in turn_costs:
            raise NoPathFoundError(
                f"No path exists between {start.name!r} and {end.name!r}."
            )

        return PathResult(
            zones=self._reconstruct_path(previous, start, end),
            total_turns=turn_costs[end.name],
        )

    @staticmethod
    def _reconstruct_path(
        previous: dict[str, Zone], start: Zone, end: Zone
    ) -> list[Zone]:
        """Reconstruct the zone sequence from the Dijkstra predecessor map.

        Args:
            previous: Mapping of zone name to its predecessor zone on the
                cheapest known path.
            start: The path's starting zone.
            end: The path's ending zone.

        Returns:
            The ordered list of zones from start to end, inclusive.
        """
        path: list[Zone] = [end]
        current = end
        while current.name != start.name:
            current = previous[current.name]
            path.append(current)
        path.reverse()
        return path
