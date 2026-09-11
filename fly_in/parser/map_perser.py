"""Parser for the Fly-in map file format.

Converts a text map description into a fully validated Network of Zone and
Connection objects, plus the declared drone count. No external parsing or
graph libraries are used; parsing is done with plain string handling and
regular expressions from the standard library.
"""

from __future__ import annotations

import re
from pathlib import Path

from exceptions import MapParsingError
from models.connection import Connection
from models.network import Network
from models.zone import Zone, ZoneType

_METADATA_PATTERN = re.compile(r"\[(?P<body>[^\]]*)\]")
_ZONE_NAME_PATTERN = re.compile(r"^[^\s\-]+$")
_VALID_ZONE_TYPES = {zt.value for zt in ZoneType}


class ParsedMap:
    """The result of parsing a map file.

    Attributes:
        network: The fully built and validated Network.
        nb_drones: The number of drones declared in the map file.
    """

    def __init__(self, network: Network, nb_drones: int) -> None:
        """Initialize a ParsedMap.

        Args:
            network: The parsed Network.
            nb_drones: The declared number of drones.
        """
        self.network = network
        self.nb_drones = nb_drones


class MapParser:
    """Parses Fly-in map files into Network instances.

    Usage:
        parser = MapParser()
        parsed = parser.parse(Path("maps/easy_1.txt"))
    """

    def parse(self, path: Path) -> ParsedMap:
        """Parse a map file from disk.

        Args:
            path: Path to the map file to parse.

        Returns:
            A ParsedMap containing the built Network and drone count.

        Raises:
            MapParsingError: If the file cannot be read or violates the
                expected format.
        """
        try:
            raw_text = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise MapParsingError(f"Could not read map file {path}: {exc}")

        return self.parse_text(raw_text)

    def parse_text(self, text: str) -> ParsedMap:
        """Parse map content already loaded as a string.

        Args:
            text: The full contents of a map file.

        Returns:
            A ParsedMap containing the built Network and drone count.

        Raises:
            MapParsingError: If the content violates the expected format.
        """
        lines = text.splitlines()
        network = Network()
        nb_drones: int | None = None
        seen_connection_names: set[str] = set()

        for line_number, raw_line in enumerate(lines, start=1):
            line = self._strip_comment(raw_line).strip()
            if not line:
                continue

            if nb_drones is None:
                nb_drones = self._parse_nb_drones(line, line_number)
                continue

            if line.startswith(("start_hub:", "end_hub:", "hub:")):
                zone = self._parse_zone_line(line, line_number)
                network.add_zone(zone)
            elif line.startswith("connection:"):
                self._parse_connection_line(
                    line, line_number, network, seen_connection_names
                )
            else:
                raise MapParsingError(
                    "Unrecognized line; expected 'start_hub:', 'end_hub:', "
                    "'hub:', or 'connection:'.",
                    line_number=line_number,
                    raw_line=raw_line,
                )

        if nb_drones is None:
            raise MapParsingError(
                "Map file is empty; expected 'nb_drones: <positive_integer>' "
                "as the first line."
            )

        network.validate()
        return ParsedMap(network=network, nb_drones=nb_drones)

    @staticmethod
    def _strip_comment(raw_line: str) -> str:
        """Remove a trailing '#' comment from a line, if present.

        Args:
            raw_line: The raw line, possibly containing a comment.

        Returns:
            The line with any comment removed.
        """
        hash_index = raw_line.find("#")
        if hash_index == -1:
            return raw_line
        return raw_line[:hash_index]

    @staticmethod
    def _parse_nb_drones(line: str, line_number: int) -> int:
        """Parse the 'nb_drones: <positive_integer>' declaration line.

        Args:
            line: The comment-stripped, trimmed line content.
            line_number: The 1-indexed source line number, for errors.

        Returns:
            The declared number of drones.

        Raises:
            MapParsingError: If the line is malformed or the value is not
                a positive integer.
        """
        match = re.match(r"^nb_drones:\s*(\S+)$", line)
        if not match:
            raise MapParsingError(
                "Expected 'nb_drones: <positive_integer>' as the first "
                "meaningful line.",
                line_number=line_number,
                raw_line=line,
            )
        value_text = match.group(1)
        if not value_text.isdigit() or int(value_text) <= 0:
            raise MapParsingError(
                "nb_drones must be a positive integer.",
                line_number=line_number,
                raw_line=line,
            )
        return int(value_text)

    def _parse_zone_line(self, line: str, line_number: int) -> Zone:
        """Parse a 'start_hub:' / 'end_hub:' / 'hub:' zone definition line.

        Args:
            line: The comment-stripped, trimmed line content.
            line_number: The 1-indexed source line number, for errors.

        Returns:
            The constructed Zone.

        Raises:
            MapParsingError: If the line is malformed, coordinates are not
                valid integers, the zone name is invalid, or metadata is
                invalid.
        """
        prefix, _, rest = line.partition(":")
        is_start = prefix == "start_hub"
        is_end = prefix == "end_hub"

        metadata_match = _METADATA_PATTERN.search(rest)
        metadata_body = metadata_match.group("body") if metadata_match else ""
        header = (
            rest[: metadata_match.start()] if metadata_match else rest
        ).strip()

        tokens = header.split()
        if len(tokens) != 3:
            raise MapParsingError(
                "Expected '<name> <x> <y>' after zone prefix.",
                line_number=line_number,
                raw_line=line,
            )
        name, x_text, y_text = tokens

        if not _ZONE_NAME_PATTERN.match(name):
            raise MapParsingError(
                "Zone names must not contain dashes or whitespace.",
                line_number=line_number,
                raw_line=line,
            )
        if not self._is_valid_integer(x_text) or not self._is_valid_integer(
            y_text
        ):
            raise MapParsingError(
                "Zone coordinates must be valid integers.",
                line_number=line_number,
                raw_line=line,
            )

        metadata = self._parse_metadata(metadata_body, line_number, line)
        zone_type = self._parse_zone_type(metadata, line_number, line)
        max_drones = self._parse_positive_int(
            metadata.get("max_drones"), "max_drones", line_number, line
        )

        return Zone(
            name=name,
            x=int(x_text),
            y=int(y_text),
            zone_type=zone_type,
            color=metadata.get("color"),
            max_drones=max_drones if max_drones is not None else 1,
            is_start=is_start,
            is_end=is_end,
        )

    def _parse_connection_line(
        self,
        line: str,
        line_number: int,
        network: Network,
        seen_connection_names: set[str],
    ) -> None:
        """Parse a 'connection:' line and register it on the network.

        Args:
            line: The comment-stripped, trimmed line content.
            line_number: The 1-indexed source line number, for errors.
            network: The Network to register the connection on.
            seen_connection_names: A set of canonical connection names seen
                so far, used to reject duplicates.

        Raises:
            MapParsingError: If the line is malformed, references unknown
                zones, or duplicates an existing connection.
        """
        _, _, rest = line.partition(":")
        metadata_match = _METADATA_PATTERN.search(rest)
        metadata_body = metadata_match.group("body") if metadata_match else ""
        header = (
            rest[: metadata_match.start()] if metadata_match else rest
        ).strip()

        if "-" not in header:
            raise MapParsingError(
                "Expected 'connection: <zone1>-<zone2>'.",
                line_number=line_number,
                raw_line=line,
            )
        left_name, _, right_name = header.partition("-")
        left_name, right_name = left_name.strip(), right_name.strip()
        if not left_name or not right_name:
            raise MapParsingError(
                "Connection must reference two non-empty zone names.",
                line_number=line_number,
                raw_line=line,
            )

        try:
            zone_a = network.get_zone(left_name)
            zone_b = network.get_zone(right_name)
        except Exception as exc:
            raise MapParsingError(
                f"Connection references undefined zone: {exc}",
                line_number=line_number,
                raw_line=line,
            ) from exc

        canonical_name = "-".join(sorted((left_name, right_name)))
        if canonical_name in seen_connection_names:
            raise MapParsingError(
                "Duplicate connection (a-b and b-a are considered the "
                "same connection).",
                line_number=line_number,
                raw_line=line,
            )

        metadata = self._parse_metadata(metadata_body, line_number, line)
        max_link_capacity = self._parse_positive_int(
            metadata.get("max_link_capacity"),
            "max_link_capacity",
            line_number,
            line,
        )

        try:
            network.add_connection(
                Connection(
                    zone_a,
                    zone_b,
                    max_link_capacity=(
                        max_link_capacity
                        if max_link_capacity is not None
                        else 1
                    ),
                )
            )
        except Exception as exc:
            raise MapParsingError(
                str(exc), line_number=line_number, raw_line=line
            ) from exc

        seen_connection_names.add(canonical_name)

    @staticmethod
    def _parse_metadata(
        body: str, line_number: int, raw_line: str
    ) -> dict[str, str]:
        """Parse a metadata block body into a key-value mapping.

        Args:
            body: The raw content between '[' and ']', e.g.
                "zone=priority color=green max_drones=2".
            line_number: The 1-indexed source line number, for errors.
            raw_line: The full raw line, for error context.

        Returns:
            A dictionary mapping metadata keys to their string values.

        Raises:
            MapParsingError: If any metadata token is not a valid
                'key=value' pair.
        """
        metadata: dict[str, str] = {}
        for token in body.split():
            if "=" not in token:
                raise MapParsingError(
                    f"Invalid metadata token {token!r}; expected "
                    "'key=value'.",
                    line_number=line_number,
                    raw_line=raw_line,
                )
            key, _, value = token.partition("=")
            if not key or not value:
                raise MapParsingError(
                    f"Invalid metadata token {token!r}; expected "
                    "'key=value'.",
                    line_number=line_number,
                    raw_line=raw_line,
                )
            metadata[key] = value
        return metadata

    @staticmethod
    def _parse_zone_type(
        metadata: dict[str, str], line_number: int, raw_line: str
    ) -> ZoneType:
        """Resolve the ZoneType from a metadata mapping.

        Args:
            metadata: The parsed metadata key-value mapping.
            line_number: The 1-indexed source line number, for errors.
            raw_line: The full raw line, for error context.

        Returns:
            The resolved ZoneType, defaulting to NORMAL if unspecified.

        Raises:
            MapParsingError: If the 'zone' metadata value is not a
                recognized zone type.
        """
        value = metadata.get("zone", ZoneType.NORMAL.value)
        if value not in _VALID_ZONE_TYPES:
            raise MapParsingError(
                f"Invalid zone type {value!r}; must be one of "
                f"{sorted(_VALID_ZONE_TYPES)}.",
                line_number=line_number,
                raw_line=raw_line,
            )
        return ZoneType(value)

    @staticmethod
    def _parse_positive_int(
        value: str | None, field_name: str, line_number: int, raw_line: str
    ) -> int | None:
        """Parse an optional metadata value as a positive integer.

        Args:
            value: The raw string value, or None if the field was absent.
            field_name: The metadata field name, used in error messages.
            line_number: The 1-indexed source line number, for errors.
            raw_line: The full raw line, for error context.

        Returns:
            The parsed positive integer, or None if value was None.

        Raises:
            MapParsingError: If the value is present but not a positive
                integer.
        """
        if value is None:
            return None
        if not value.isdigit() or int(value) <= 0:
            raise MapParsingError(
                f"{field_name} must be a positive integer.",
                line_number=line_number,
                raw_line=raw_line,
            )
        return int(value)

    @staticmethod
    def _is_valid_integer(text: str) -> bool:
        """Check whether a string represents a valid, optionally signed
        integer.

        Args:
            text: The string to check.

        Returns:
            True if the string is a valid integer literal.
        """
        return bool(re.match(r"^-?\d+$", text))
