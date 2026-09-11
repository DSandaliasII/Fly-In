from __future__ import annotations

import re

from models.network import Network
from models.zone import Zone, ZoneType
from simulation.simulator import SimulationResult

_RESET = "\033[0m"
_BOLD = "\033[1m"

_NAMED_COLOR_CODES: dict[str, str] = {
    "red": "\033[31m",
    "green": "\033[32m",
    "yellow": "\033[33m",
    "blue": "\033[34m",
    "magenta": "\033[35m",
    "cyan": "\033[36m",
    "white": "\033[37m",
    "gray": "\033[90m",
    "grey": "\033[90m",
    "black": "\033[30m",
}

_ZONE_TYPE_DEFAULT_COLOR: dict[ZoneType, str] = {
    ZoneType.NORMAL: "\033[37m",
    ZoneType.PRIORITY: "\033[32m",
    ZoneType.RESTRICTED: "\033[31m",
    ZoneType.BLOCKED: "\033[90m",
}

_TRANSIT_COLOR = "\033[35m"

_MOVE_PATTERN = re.compile(r"^(?P<drone_id>D\d+)-(?P<destination>.+)$")


class TerminalView:
    """Renders a SimulationResult as colored text in the terminal.

    Attributes:
        network: The Network the simulation ran on, used to resolve zone
            colors and types for each movement.
    """

    def __init__(self, network: Network) -> None:
        """Initialize the TerminalView.

        Args:
            network: The Network the simulation ran on.
        """
        self.network = network

    def render(self, result: SimulationResult) -> str:
        """Render a full colored report for a simulation result.

        Args:
            result: The SimulationResult to render.

        Returns:
            The complete colored report as a single string, ready to be
            printed to the terminal.
        """
        sections = [
            self._render_legend(),
            self._render_turns(result),
            self._render_summary(result),
        ]
        return "\n\n".join(sections)

    def _render_legend(self) -> str:
        """Render a legend mapping zone types to their display color.

        Returns:
            A formatted legend string.
        """
        lines = [f"{_BOLD}Zone legend:{_RESET}"]
        for zone_type in ZoneType:
            code = _ZONE_TYPE_DEFAULT_COLOR[zone_type]
            lines.append(f"  {code}{zone_type.value}{_RESET}")
        lines.append(f"  {_TRANSIT_COLOR}in transit (restricted){_RESET}")
        return "\n".join(lines)

    def _render_turns(self, result: SimulationResult) -> str:
        """Render each simulation turn as a colored, numbered line.

        Args:
            result: The SimulationResult whose turn log will be rendered.

        Returns:
            A formatted, multi-line string with one line per turn.
        """
        lines = [f"{_BOLD}Simulation:{_RESET}"]
        width = len(str(len(result.turn_log)))
        for index, moves in enumerate(result.turn_log, start=1):
            colored_moves = " ".join(self._colorize_move(m) for m in moves)
            lines.append(f"  turn {index:>{width}}: {colored_moves}")
        return "\n".join(lines)

    def _colorize_move(self, move: str) -> str:
        """Colorize a single "D<id>-<destination>" movement string.

        Args:
            move: The raw movement string.

        Returns:
            The movement string wrapped in ANSI color codes based on the
            destination's zone color (if it is a zone) or a distinct
            "in transit" color if the destination is a connection name.
        """
        match = _MOVE_PATTERN.match(move)
        if not match:
            return move

        destination = match.group("destination")
        zone = self.network.zones.get(destination)
        color = self._resolve_color(zone) if zone else _TRANSIT_COLOR
        return f"{color}{move}{_RESET}"

    @staticmethod
    def _resolve_color(zone: Zone) -> str:
        """Resolve the ANSI color code to use for a given zone.

        Args:
            zone: The zone to resolve a display color for.

        Returns:
            An ANSI color escape code, preferring the zone's explicit
            color metadata and falling back to a default based on zone
            type.
        """
        if zone.color and zone.color.lower() in _NAMED_COLOR_CODES:
            return _NAMED_COLOR_CODES[zone.color.lower()]
        return _ZONE_TYPE_DEFAULT_COLOR[zone.zone_type]

    def _render_summary(self, result: SimulationResult) -> str:
        """Render the summary statistics block.

        Args:
            result: The SimulationResult to summarize.

        Returns:
            A formatted summary string.
        """
        lines = [
            f"{_BOLD}Summary:{_RESET}",
            f"  Drones delivered:        {result.nb_drones}",
            f"  Total turns:             {result.total_turns}",
            "  Average turns per drone: "
            f"{result.average_turns_per_drone:.2f}",
        ]
        return "\n".join(lines)
