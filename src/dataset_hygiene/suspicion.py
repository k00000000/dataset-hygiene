from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from .models import FileRecord, NameCollision


def find_name_collisions(records: list[FileRecord]) -> list[NameCollision]:
    by_name: dict[str, list[FileRecord]] = defaultdict(list)
    for record in records:
        if record.broken_symlink:
            continue
        basename = Path(record.path).name
        by_name[basename].append(record)

    collisions: list[NameCollision] = []
    for basename, items in sorted(by_name.items()):
        if len(items) < 2:
            continue
        hashes = {item.sha256 for item in items}
        if len(hashes) <= 1:
            # Same basename and identical content is already covered by duplicate groups.
            continue
        collisions.append(
            NameCollision(
                basename=basename,
                paths=sorted(item.path for item in items),
                sha256s=sorted(hashes),
            )
        )
    return collisions


def find_suspicious_extensions(
    records: list[FileRecord],
    suspicious: set[str],
) -> list[str]:
    normalized = {item.lower() if item.startswith(".") else f".{item.lower()}" for item in suspicious}
    hits = [
        record.path
        for record in records
        if not record.broken_symlink and record.suffix.lower() in normalized
    ]
    return sorted(hits)


def find_tiny_files(records: list[FileRecord], threshold: int) -> list[str]:
    if threshold < 0:
        return []
    return sorted(
        record.path
        for record in records
        if not record.broken_symlink and 0 < record.size <= threshold
    )
