"""Command-line entry point for the Fly-in drone routing simulator.

Usage:
    python main.py <map_file> [--max-turns N]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from exceptions import FlyInError
from parser.map_parser import MapParser
from simulation.simulator import Simulator, SimulationResult


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
    return parser


def run(map_file: Path, max_turns: int | None) -> SimulationResult:
    """Parse a map file and run the full simulation.

    Args:
        map_file: Path to the map file to load.
        max_turns: Optional hard cap on the number of simulated turns.

    Returns:
        The SimulationResult describing the completed run.

    Raises:
        FlyInError: If parsing fails, no path exists, or the scheduler
            cannot resolve a deadlock within the turn budget.
    """
    parsed = MapParser().parse(map_file)
    simulator = Simulator(parsed.network, parsed.nb_drones)
    return simulator.run(max_turns=max_turns)


def print_report(result: SimulationResult) -> None:
    """Print the simulation output and summary metrics to stdout.

    Args:
        result: The SimulationResult to display.
    """
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
        result = run(args.map_file, args.max_turns)
    except FlyInError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print_report(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
