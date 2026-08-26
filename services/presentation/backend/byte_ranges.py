from __future__ import annotations

from dataclasses import dataclass


class RangeNotSatisfiable(ValueError):
    pass


@dataclass(frozen=True)
class ByteRange:
    start: int
    end: int

    @property
    def length(self) -> int:
        return self.end - self.start + 1


def parse_byte_range(value: str | None, *, total_size: int) -> ByteRange | None:
    """Parse the single byte-range form supported by PDF and PMTiles delivery."""
    if value is None:
        return None
    if total_size <= 0 or not value.startswith("bytes="):
        raise RangeNotSatisfiable

    range_spec = value[6:].strip()
    if not range_spec or "," in range_spec:
        raise RangeNotSatisfiable
    start_raw, separator, end_raw = range_spec.partition("-")
    if not separator:
        raise RangeNotSatisfiable

    try:
        if not start_raw:
            suffix_size = int(end_raw)
            if suffix_size <= 0:
                raise RangeNotSatisfiable
            start = max(total_size - suffix_size, 0)
            end = total_size - 1
        else:
            start = int(start_raw)
            end = int(end_raw) if end_raw else total_size - 1
    except ValueError as exc:
        raise RangeNotSatisfiable from exc

    if start < 0 or end < start or start >= total_size:
        raise RangeNotSatisfiable
    return ByteRange(start=start, end=min(end, total_size - 1))
