from __future__ import annotations

from pathlib import Path
from typing import Iterable

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp", ".tif", ".tiff"}


def pillow_available() -> bool:
    try:
        import PIL  # noqa: F401

        return True
    except ImportError:
        return False


def average_hash(path: Path, hash_size: int = 8) -> str | None:
    """Compute a simple average perceptual hash. Returns None if Pillow is missing or decode fails."""
    try:
        from PIL import Image
    except ImportError:
        return None

    try:
        with Image.open(path) as image:
            gray = image.convert("L").resize((hash_size, hash_size), Image.Resampling.LANCZOS)
            pixels = list(gray.getdata())
    except OSError:
        return None

    if not pixels:
        return None
    avg = sum(pixels) / len(pixels)
    bits = "".join("1" if pixel >= avg else "0" for pixel in pixels)
    # Pack bits into hex for compact storage.
    value = int(bits, 2)
    width = (hash_size * hash_size + 3) // 4
    return f"{value:0{width}x}"


def hamming_distance(left: str, right: str) -> int:
    if len(left) != len(right):
        raise ValueError("Hash strings must have equal length")
    left_int = int(left, 16)
    right_int = int(right, 16)
    return (left_int ^ right_int).bit_count()


def group_near_duplicates(
    path_to_hash: dict[str, str],
    *,
    max_distance: int = 5,
) -> list[list[str]]:
    """Greedy clustering of paths whose perceptual hashes are within max_distance."""
    items = sorted(path_to_hash.items(), key=lambda item: item[0])
    used: set[str] = set()
    groups: list[list[str]] = []

    for index, (path, digest) in enumerate(items):
        if path in used:
            continue
        cluster = [path]
        used.add(path)
        for other_path, other_digest in items[index + 1 :]:
            if other_path in used:
                continue
            if hamming_distance(digest, other_digest) <= max_distance:
                cluster.append(other_path)
                used.add(other_path)
        if len(cluster) > 1:
            groups.append(sorted(cluster))

    groups.sort(key=lambda group: (-len(group), group[0]))
    return groups


def is_image_path(path: Path | str, suffixes: Iterable[str] | None = None) -> bool:
    suffix = Path(path).suffix.lower()
    allowed = set(suffixes) if suffixes is not None else IMAGE_SUFFIXES
    return suffix in allowed
