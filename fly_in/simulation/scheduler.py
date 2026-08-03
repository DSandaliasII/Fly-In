"""Turn-by-turn multi-drone conflict scheduler.

The Scheduler takes drones that already have a planned path (assigned by the
Pathfinder) and advances the simulation one turn at a time, resolving
capacity conflicts between drones competing for the same zone or connection.
It reasons in terms of (zone, turn) and (connection, turn) reservations: a
drone that cannot safely make its next move waits, and drones committed to a
multi-turn restricted-zone transit are tracked so their reserved connection
and destination capacity is respected by everyone else.
"""

from __future__ import annotations

import re
from collections import defaultdict

from exceptions import DeadlockError
from models.drone import Drone, DroneState
from models.network import Network

_DRONE_ID_NUMBER = re.compile(r"(\d+)")


def _priority_key(drone: Drone) -> tuple[int, str]:
    """Compute a stable ordering key used to resolve movement conflicts.

    Drones are ordered primarily by the numeric portion of their ID (so
    "D2" sorts before "D10"), falling back to the full ID string for
    non-numeric or malformed identifiers.

    Args:
        drone: The drone to compute a key for.

    Returns:
        A tuple usable as a sort key.
    """
    match = _DRONE_ID_NUMBER.search(drone.drone_id)
    numeric_part = int(match.group(1)) if match else 0
    return (numeric_part, drone.drone_id)


class Scheduler:
    """Runs the turn-by-turn simulation for a set of drones on a Network.

    Attributes:
        network: The Network the drones move through.
        drones: The drones being scheduled. Each must already have a path
            assigned via Drone.assign_path before calling run().
    """

    def __init__(self, network: Network, drones: list[Drone]) -> None:
        """Initialize the Scheduler.

        Args:
            network: The Network the drones move through.
            drones: The drones to schedule, each with a path pre-assigned.
        """
        self.network = network
        self.drones = drones

    def run(self, max_turns: int | None = None) -> list[list[str]]:
        """Run the simulation until all drones are delivered.

        Args:
            max_turns: An optional hard cap on the number of turns to
                simulate before giving up. Defaults to a generous heuristic
                based on network size and drone count if not provided.

        Returns:
            A list of turns, each turn being a list of movement strings in
            the format "D<id>-<zone>" or "D<id>-<connection>", following
            the order they were committed within that turn.

        Raises:
            DeadlockError: If no drone is able to make progress for an
                extended number of consecutive turns.
        """
        if max_turns is None:
            max_turns = max(50, len(self.network) * len(self.drones) * 4)

        active_transits: dict[str, int] = defaultdict(int)
        reserved_arrivals: dict[str, int] = defaultdict(int)
        turn_log: list[list[str]] = []
        stalled_turns = 0
        turn = 0

        while not self._all_delivered():
            turn += 1
            if turn > max_turns:
                raise DeadlockError(
                    f"Simulation exceeded the maximum of {max_turns} turns "
                    "without delivering all drones."
                )

            zone_occupancy = self._current_zone_occupancy()
            connection_usage: dict[str, int] = dict(active_transits)
            acted: set[str] = set()
            turn_moves: list[tuple[int, str]] = []

            self._advance_in_transit_drones(
                zone_occupancy,
                active_transits,
                reserved_arrivals,
                acted,
                turn_moves,
            )
            self._process_waiting_drones(
                zone_occupancy,
                connection_usage,
                active_transits,
                reserved_arrivals,
                acted,
                turn_moves,
            )

            if turn_moves:
                stalled_turns = 0
            else:
                stalled_turns += 1
                if stalled_turns > max(10, len(self.drones) * 2):
                    raise DeadlockError(
                        "No drone made progress for "
                        f"{stalled_turns} consecutive turns; likely "
                        "deadlock."
                    )

            turn_moves.sort(key=lambda item: item[0])
            turn_log.append([entry for _, entry in turn_moves])

        return turn_log

    def _all_delivered(self) -> bool:
        """Return True if every drone has reached the end zone."""
        return all(drone.is_delivered for drone in self.drones)

    def _current_zone_occupancy(self) -> dict[str, int]:
        """Count drones currently resident in each zone.

        Drones that are mid-transit on a restricted-zone connection are
        not counted, since they do not physically occupy either endpoint
        zone while in flight.

        Returns:
            A mapping of zone name to the number of resident drones.
        """
        occupancy: dict[str, int] = defaultdict(int)
        for drone in self.drones:
            if drone.is_delivered:
                continue
            if drone.state is DroneState.IN_TRANSIT:
                continue
            occupancy[drone.current_zone.name] += 1
        return occupancy

    def _advance_in_transit_drones(
        self,
        zone_occupancy: dict[str, int],
        active_transits: dict[str, int],
        reserved_arrivals: dict[str, int],
        acted: set[str],
        turn_moves: list[tuple[int, str]],
    ) -> None:
        """Advance drones already committed to a multi-turn transit.

        These drones cannot wait or be rerouted mid-transit, so they are
        always processed unconditionally before any new moves are decided.

        Args:
            zone_occupancy: Current per-zone resident drone counts, updated
                in place as drones arrive.
            active_transits: Per-connection count of drones currently in
                flight, updated in place as drones complete their transit.
            reserved_arrivals: Per-zone count of guaranteed upcoming
                arrivals, updated in place as reservations resolve.
            acted: Set of drone IDs that have already acted this turn,
                updated in place.
            turn_moves: Accumulator of (priority, movement string) pairs
                for this turn, updated in place.
        """
        for drone in sorted(self.drones, key=_priority_key):
            if drone.is_delivered or drone.state is not DroneState.IN_TRANSIT:
                continue

            connection = drone.in_transit_connection
            assert connection is not None  # guaranteed by IN_TRANSIT state

            arrived = drone.advance_transit()
            acted.add(drone.drone_id)
            priority = _priority_key(drone)[0]

            if arrived:
                active_transits[connection.name] -= 1
                reserved_arrivals[drone.current_zone.name] -= 1
                zone_occupancy[drone.current_zone.name] += 1
                turn_moves.append(
                    (priority, f"{drone.drone_id}-{drone.current_zone.name}")
                )
            else:
                turn_moves.append(
                    (priority, f"{drone.drone_id}-{connection.name}")
                )

    def _process_waiting_drones(
        self,
        zone_occupancy: dict[str, int],
        connection_usage: dict[str, int],
        active_transits: dict[str, int],
        reserved_arrivals: dict[str, int],
        acted: set[str],
        turn_moves: list[tuple[int, str]],
    ) -> None:
        """Decide moves for drones that are not mid-transit.

        Args:
            zone_occupancy: Current per-zone resident drone counts, updated
                in place as drones depart and arrive.
            connection_usage: Per-connection usage for this turn (including
                ongoing transits), updated in place.
            active_transits: Per-connection count of drones currently in
                flight, updated in place for newly started transits.
            reserved_arrivals: Per-zone count of guaranteed upcoming
                arrivals, updated in place for newly reserved transits.
            acted: Set of drone IDs that have already acted this turn,
                updated in place.
            turn_moves: Accumulator of (priority, movement string) pairs
                for this turn, updated in place.
        """
        for drone in sorted(self.drones, key=_priority_key):
            if drone.is_delivered or drone.drone_id in acted:
                continue

            next_zone = drone.next_zone
            if next_zone is None:
                continue

            connection = self.network.get_connection(
                drone.current_zone, next_zone
            )
            cost = next_zone.movement_cost
            conn_usage = connection_usage.get(connection.name, 0)
            priority = _priority_key(drone)[0]

            if cost == 1:
                dest_occupancy = zone_occupancy.get(next_zone.name, 0)
                can_move = next_zone.can_accept(
                    dest_occupancy
                ) and connection.can_accept(conn_usage)

                if can_move:
                    zone_occupancy[drone.current_zone.name] -= 1
                    drone.move_to(next_zone)
                    zone_occupancy[next_zone.name] = dest_occupancy + 1
                    connection_usage[connection.name] = conn_usage + 1
                    turn_moves.append(
                        (priority, f"{drone.drone_id}-{next_zone.name}")
                    )
                else:
                    drone.wait()
            else:
                dest_pressure = zone_occupancy.get(
                    next_zone.name, 0
                ) + reserved_arrivals.get(next_zone.name, 0)
                can_start = connection.can_accept(
                    conn_usage
                ) and next_zone.can_accept(dest_pressure)

                if can_start:
                    zone_occupancy[drone.current_zone.name] -= 1
                    drone.begin_transit(connection, next_zone, turns=cost)
                    drone.advance_transit()
                    active_transits[connection.name] += 1
                    connection_usage[connection.name] = conn_usage + 1
                    reserved_arrivals[next_zone.name] += 1
                    turn_moves.append(
                        (priority, f"{drone.drone_id}-{connection.name}")
                    )
                else:
                    drone.wait()

            acted.add(drone.drone_id)
