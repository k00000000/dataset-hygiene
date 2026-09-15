from __future__ import annotations

import hashlib
from pathlib import Path


DEFAULT_SKIP_DIR_NAMES = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "__pycache__",
    "node_modules",
    ".pytest_cache",
}


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def should_skip_dir(path: Path, skip_hidden: bool, skip_dir_names: set[str]) -> bool:
    name = path.name
    if name in skip_dir_names:
        return True
    if skip_hidden and name.startswith("."):
        return True
    return False
