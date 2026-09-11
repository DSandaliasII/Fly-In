"""Command-line entry point for the Fly-in drone routing simulator.

Usage:
    python main.py <map_file> [--max-turns N] [--no-color]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from exceptions import FlyInError
from models.network import Network
from parser.map_parser import MapParser
from simulation.simulator import Simulator, SimulationResult
from visualization.terminal_view import TerminalView


def build_arg_parser() -> argparse.ArgumentParser:
    """Build the command-line argument parser.

    Returns:
        A configured ArgumentParser for the CLI.
    """
    parser = argparse.ArgumentParser(
        prog="fly-in",
        description=(
            "Route a fleet of drones from a start zone to an end zone "
            "across a network of connected zones."
        ),
    )
    parser.add_argument(
        "map_file",
        type=Path,
        help="Path to the map file describing zones and connections.",
    )
    parser.add_argument(
        "--max-turns",
        type=int,
        default=None,
        help=(
            "Hard cap on the number of simulation turns before aborting "
            "(defaults to a heuristic based on network and fleet size)."
        ),
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable colored terminal output and print plain text.",
    )
    return parser


def run(
    map_file: Path, max_turns: int | None
) -> tuple[Network, SimulationResult]:
    """Parse a map file and run the full simulation.

    Args:
        map_file: Path to the map file to load.
        max_turns: Optional hard cap on the number of simulated turns.

    Returns:
        A tuple of (the parsed Network, the SimulationResult).

    Raises:
        FlyInError: If parsing fails, no path exists, or the scheduler
            cannot resolve a deadlock within the turn budget.
    """
    parsed = MapParser().parse(map_file)
    simulator = Simulator(parsed.network, parsed.nb_drones)
    result = simulator.run(max_turns=max_turns)
    return parsed.network, result


def print_report(
    network: Network, result: SimulationResult, use_color: bool
) -> None:
    """Print the simulation output and summary metrics to stdout.

    Args:
        network: The Network the simulation ran on, needed to resolve
            zone colors when colored output is enabled.
        result: The SimulationResult to display.
        use_color: If True, render via TerminalView with ANSI colors;
            otherwise print the plain-text turn log and summary.
    """
    if use_color:
        print(TerminalView(network).render(result))
        return

    print(result.format_output())
    print()
    print(f"Drones delivered: {result.nb_drones}")
    print(f"Total turns: {result.total_turns}")
    print(f"Average turns per drone: {result.average_turns_per_drone:.2f}")


def main(argv: list[str] | None = None) -> int:
    """Run the CLI, returning a process exit code.

    Args:
        argv: Command-line arguments, excluding the program name. Defaults
            to sys.argv[1:] when None.

    Returns:
        0 on success, 1 on any FlyInError (parsing, pathfinding, or
        simulation failure).
    """
    args = build_arg_parser().parse_args(argv)

    try:
        network, result = run(args.map_file, args.max_turns)
    except FlyInError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print_report(network, result, use_color=not args.no_color)
    return 0


if __name__ == "__main__":
    sys.exit(main())
