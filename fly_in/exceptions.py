"""Custom exceptions used across the Fly-in project.

Centralizing exceptions here keeps error handling consistent between the
parser, the simulation engine, and the pathfinding module, and makes it easy
to catch specific failure modes at the boundaries (e.g. in main.py).
"""

from __future__ import annotations


class FlyInError(Exception):
    """Base class for all custom exceptions raised by this project."""


class MapParsingError(FlyInError):
    """Raised when the input map file is malformed or violates the format.

    Attributes:
        line_number: The 1-indexed line in the source file where the error
            was detected, if known.
        raw_line: The raw content of the offending line, if known.
    """

    def __init__(
        self,
        message: str,
        line_number: int | None = None,
        raw_line: str | None = None,
    ) -> None:
        """Initialize the parsing error with contextual information.

        Args:
            message: A human-readable description of the problem.
            line_number: The line number where the error occurred, if known.
            raw_line: The raw text of the offending line, if known.
        """
        self.line_number = line_number
        self.raw_line = raw_line

        full_message = message
        if line_number is not None:
            full_message = f"Line {line_number}: {message}"
        if raw_line is not None:
            full_message = f"{full_message} (got: {raw_line!r})"

        super().__init__(full_message)


class ZoneNotFoundError(FlyInError):
    """Raised when a referenced zone name does not exist in the network."""


class InvalidConnectionError(FlyInError):
    """Raised when a connection references invalid or duplicate zones."""


class NoPathFoundError(FlyInError):
    """Raised when no valid path exists between the start and end zones."""


class SimulationError(FlyInError):
    """Raised when the simulation reaches an invalid or unrecoverable state.

    This covers cases such as capacity violations that slip past scheduling
    safeguards, or a drone attempting an illegal move.
    """


class DeadlockError(SimulationError):
    """Raised when the scheduler cannot resolve a cyclic waiting condition.

    This should be rare in practice since the scheduler is expected to break
    deadlocks using priority ordering, but it exists as a safety net so the
    simulation fails loudly instead of looping forever.
    """
