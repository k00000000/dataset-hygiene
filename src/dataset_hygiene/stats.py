from __future__ import annotations

import zlib
from collections import Counter
from typing import Iterable

from .models import FileRecord

SIZE_BUCKETS: tuple[tuple[str, int], ...] = (
    ("0B", 0),
    ("1B-1KiB", 1024),
    ("1KiB-64KiB", 64 * 1024),
    ("64KiB-1MiB", 1024 * 1024),
    ("1MiB-16MiB", 16 * 1024 * 1024),
    ("16MiB-256MiB", 256 * 1024 * 1024),
    ("256MiB+", 2**63 - 1),
)


def size_bucket(size: int) -> str:
    if size <= 0:
        return "0B"
    for label, upper in SIZE_BUCKETS[1:]:
        if size <= upper:
            return label
    return "256MiB+"


def build_size_histogram(records: Iterable[FileRecord]) -> dict[str, int]:
    counter: Counter[str] = Counter()
    for record in records:
        counter[size_bucket(record.size)] += 1
    # Preserve canonical bucket order, omit empty trailing buckets only if never seen.
    ordered: dict[str, int] = {}
    for label, _ in SIZE_BUCKETS:
        if label in counter:
            ordered[label] = counter[label]
    return ordered


def top_extensions(extension_counts: dict[str, int], limit: int = 20) -> dict[str, int]:
    items = sorted(extension_counts.items(), key=lambda kv: (-kv[1], kv[0]))
    if limit <= 0:
        return dict(items)
    return dict(items[:limit])


def rough_compressibility(data: bytes) -> float | None:
    """Return 1 - compressed/raw ratio in [0, 1]. Higher means more compressible/redundant."""
    if not data:
        return None
    compressed = zlib.compress(data, level=6)
    ratio = len(compressed) / len(data)
    value = 1.0 - min(ratio, 1.0)
    return round(value, 4)


def sample_file_compressibility(path, *, sample_bytes: int = 64 * 1024) -> float | None:
    with path.open("rb") as handle:
        sample = handle.read(sample_bytes)
    return rough_compressibility(sample)
