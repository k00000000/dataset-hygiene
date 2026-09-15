from __future__ import annotations

import fnmatch
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from .config import DEFAULT_SUSPICIOUS_EXTENSIONS, HygieneConfig
from .hashutil import DEFAULT_SKIP_DIR_NAMES, sha256_file, should_skip_dir
from .models import AuditReport, FileRecord
from .phash import average_hash, group_near_duplicates, is_image_path, pillow_available
from .stats import build_size_histogram, sample_file_compressibility, top_extensions
from .suspicion import find_name_collisions, find_suspicious_extensions, find_tiny_files


def _matches_exclude(rel_posix: str, patterns: list[str]) -> bool:
    name = Path(rel_posix).name
    for pattern in patterns:
        if fnmatch.fnmatch(rel_posix, pattern) or fnmatch.fnmatch(name, pattern):
            return True
    return False


def iter_paths(
    root: Path,
    *,
    skip_hidden: bool = True,
    skip_dir_names: set[str] | None = None,
    exclude_patterns: list[str] | None = None,
) -> tuple[list[Path], list[str]]:
    """Return (regular_or_symlink_files, broken_symlink_relative_paths)."""
    skip_dirs = set(skip_dir_names or DEFAULT_SKIP_DIR_NAMES)
    patterns = list(exclude_patterns or [])
    files: list[Path] = []
    broken: list[str] = []

    for path in sorted(root.rglob("*")):
        try:
            is_symlink = path.is_symlink()
        except OSError:
            continue

        if any(should_skip_dir(parent, skip_hidden, skip_dirs) for parent in path.parents):
            continue
        if skip_hidden and path.name.startswith("."):
            continue

        try:
            rel = str(path.relative_to(root)).replace("\\", "/")
        except ValueError:
            continue

        if patterns and _matches_exclude(rel, patterns):
            continue

        if is_symlink:
            try:
                exists = path.exists()
            except OSError:
                exists = False
            if not exists:
                broken.append(rel)
                continue
            if path.is_dir():
                continue
            files.append(path)
            continue

        if path.is_file():
            files.append(path)

    return files, broken


def audit_path(
    root: str | Path,
    *,
    skip_hidden: bool = True,
    largest_n: int = 10,
    include_file_details: bool = True,
    exclude_patterns: list[str] | None = None,
    tiny_threshold: int = 64,
    suspicious_extensions: list[str] | None = None,
    perceptual_hash: bool = False,
    compute_compressibility: bool = False,
    top_extensions_n: int = 20,
    config: HygieneConfig | None = None,
) -> AuditReport:
    if config is not None:
        skip_hidden = not config.include_hidden
        largest_n = config.largest
        include_file_details = not config.summary_only
        exclude_patterns = list(config.exclude)
        tiny_threshold = config.tiny_threshold
        suspicious_extensions = list(config.suspicious_extensions)
        perceptual_hash = config.perceptual_hash
        compute_compressibility = config.compute_compressibility
        top_extensions_n = config.top_extensions

    root_path = Path(root).resolve()
    if not root_path.exists():
        raise FileNotFoundError(f"Path does not exist: {root_path}")
    if not root_path.is_dir():
        raise NotADirectoryError(f"Path is not a directory: {root_path}")

    patterns = list(exclude_patterns or [])
    files, broken_symlinks = iter_paths(
        root_path,
        skip_hidden=skip_hidden,
        exclude_patterns=patterns,
    )

    use_phash = bool(perceptual_hash and pillow_available())
    records: list[FileRecord] = []
    hash_groups: dict[str, list[str]] = defaultdict(list)
    ext_counter: Counter[str] = Counter()
    phash_map: dict[str, str] = {}
    path_to_sha: dict[str, str] = {}

    for file_path in files:
        rel = str(file_path.relative_to(root_path)).replace("\\", "/")
        is_symlink = file_path.is_symlink()
        try:
            size = file_path.stat().st_size
            digest = sha256_file(file_path)
        except OSError:
            broken_symlinks.append(rel)
            continue

        suffix = file_path.suffix.lower() or "<none>"
        phash_value = None
        if use_phash and is_image_path(file_path):
            phash_value = average_hash(file_path)
            if phash_value:
                phash_map[rel] = phash_value

        compressibility = None
        if compute_compressibility and size > 0:
            try:
                compressibility = sample_file_compressibility(file_path)
            except OSError:
                compressibility = None

        record = FileRecord(
            path=rel,
            size=size,
            sha256=digest,
            suffix=suffix,
            empty=size == 0,
            is_symlink=is_symlink,
            broken_symlink=False,
            phash=phash_value,
            compressibility=compressibility,
        )
        records.append(record)
        hash_groups[digest].append(rel)
        path_to_sha[rel] = digest
        ext_counter[suffix] += 1

    empty_files = [item.path for item in records if item.empty]
    duplicate_groups = [
        sorted(paths)
        for paths in hash_groups.values()
        if len(paths) > 1
    ]
    duplicate_groups.sort(key=lambda group: (-len(group), group[0]))

    near_duplicate_groups: list[list[str]] = []
    if use_phash and phash_map:
        near_duplicate_groups = group_near_duplicates(phash_map)
        cleaned: list[list[str]] = []
        for group in near_duplicate_groups:
            group_hashes = {path_to_sha[path] for path in group}
            # Skip clusters that are only exact duplicates (already reported).
            if len(group_hashes) == 1:
                continue
            cleaned.append(group)
        near_duplicate_groups = cleaned

    largest = sorted(records, key=lambda item: item.size, reverse=True)[: max(largest_n, 0)]
    largest_files = [{"path": item.path, "size": item.size} for item in largest]

    if top_extensions_n <= 0:
        extension_counts = dict(sorted(ext_counter.items(), key=lambda kv: (-kv[1], kv[0])))
    else:
        extension_counts = top_extensions(dict(ext_counter), limit=top_extensions_n)

    suspicious_set = set(
        suspicious_extensions
        if suspicious_extensions is not None
        else DEFAULT_SUSPICIOUS_EXTENSIONS
    )

    return AuditReport(
        root=str(root_path),
        file_count=len(records),
        total_bytes=sum(item.size for item in records),
        empty_files=empty_files,
        tiny_files=find_tiny_files(records, tiny_threshold),
        broken_symlinks=sorted(set(broken_symlinks)),
        suspicious_extensions=find_suspicious_extensions(records, suspicious_set),
        name_collisions=find_name_collisions(records),
        duplicate_groups=duplicate_groups,
        near_duplicate_groups=near_duplicate_groups,
        extension_counts=extension_counts,
        size_histogram=build_size_histogram(records),
        largest_files=largest_files,
        files=records if include_file_details else [],
        generated_at=datetime.now(timezone.utc).isoformat(),
        perceptual_hash_enabled=use_phash,
        compressibility_enabled=compute_compressibility,
        tiny_threshold=tiny_threshold,
        exclude_patterns=patterns,
    )
