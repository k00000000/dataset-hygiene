from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class FileRecord:
    path: str
    size: int
    sha256: str
    suffix: str
    empty: bool
    is_symlink: bool = False
    broken_symlink: bool = False
    phash: str | None = None
    compressibility: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class NameCollision:
    basename: str
    paths: list[str]
    sha256s: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DiffEntry:
    path: str
    old_sha256: str | None = None
    new_sha256: str | None = None
    old_size: int | None = None
    new_size: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DiffReport:
    left: str
    right: str
    added: list[DiffEntry] = field(default_factory=list)
    removed: list[DiffEntry] = field(default_factory=list)
    changed: list[DiffEntry] = field(default_factory=list)
    unchanged_count: int = 0

    @property
    def has_differences(self) -> bool:
        return bool(self.added or self.removed or self.changed)

    def summary(self) -> dict[str, Any]:
        return {
            "left": self.left,
            "right": self.right,
            "added_count": len(self.added),
            "removed_count": len(self.removed),
            "changed_count": len(self.changed),
            "unchanged_count": self.unchanged_count,
            "has_differences": self.has_differences,
        }

    def to_dict(self) -> dict[str, Any]:
        payload = self.summary()
        payload["added"] = [item.to_dict() for item in self.added]
        payload["removed"] = [item.to_dict() for item in self.removed]
        payload["changed"] = [item.to_dict() for item in self.changed]
        return payload


@dataclass
class Manifest:
    version: int
    root: str
    generated_at: str
    file_count: int
    total_bytes: int
    files: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "root": self.root,
            "generated_at": self.generated_at,
            "file_count": self.file_count,
            "total_bytes": self.total_bytes,
            "files": self.files,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Manifest:
        return cls(
            version=int(data.get("version", 1)),
            root=str(data.get("root", "")),
            generated_at=str(data.get("generated_at", "")),
            file_count=int(data.get("file_count", len(data.get("files", [])))),
            total_bytes=int(data.get("total_bytes", 0)),
            files=list(data.get("files", [])),
        )


@dataclass
class AuditReport:
    root: str
    file_count: int
    total_bytes: int
    empty_files: list[str] = field(default_factory=list)
    tiny_files: list[str] = field(default_factory=list)
    broken_symlinks: list[str] = field(default_factory=list)
    suspicious_extensions: list[str] = field(default_factory=list)
    name_collisions: list[NameCollision] = field(default_factory=list)
    duplicate_groups: list[list[str]] = field(default_factory=list)
    near_duplicate_groups: list[list[str]] = field(default_factory=list)
    extension_counts: dict[str, int] = field(default_factory=dict)
    size_histogram: dict[str, int] = field(default_factory=dict)
    largest_files: list[dict[str, Any]] = field(default_factory=list)
    files: list[FileRecord] = field(default_factory=list)
    generated_at: str = ""
    perceptual_hash_enabled: bool = False
    compressibility_enabled: bool = False
    tiny_threshold: int = 64
    exclude_patterns: list[str] = field(default_factory=list)

    @property
    def duplicate_file_count(self) -> int:
        return sum(len(group) for group in self.duplicate_groups)

    @property
    def near_duplicate_file_count(self) -> int:
        return sum(len(group) for group in self.near_duplicate_groups)

    @property
    def has_issues(self) -> bool:
        return bool(
            self.empty_files
            or self.duplicate_groups
            or self.broken_symlinks
            or self.tiny_files
            or self.suspicious_extensions
            or self.name_collisions
            or self.near_duplicate_groups
        )

    def summary(self) -> dict[str, Any]:
        return {
            "root": self.root,
            "generated_at": self.generated_at,
            "file_count": self.file_count,
            "total_bytes": self.total_bytes,
            "empty_file_count": len(self.empty_files),
            "tiny_file_count": len(self.tiny_files),
            "broken_symlink_count": len(self.broken_symlinks),
            "suspicious_extension_count": len(self.suspicious_extensions),
            "name_collision_count": len(self.name_collisions),
            "duplicate_group_count": len(self.duplicate_groups),
            "duplicate_file_count": self.duplicate_file_count,
            "near_duplicate_group_count": len(self.near_duplicate_groups),
            "near_duplicate_file_count": self.near_duplicate_file_count,
            "extension_counts": self.extension_counts,
            "size_histogram": self.size_histogram,
            "largest_files": self.largest_files,
            "perceptual_hash_enabled": self.perceptual_hash_enabled,
            "compressibility_enabled": self.compressibility_enabled,
            "tiny_threshold": self.tiny_threshold,
            "exclude_patterns": self.exclude_patterns,
            "has_issues": self.has_issues,
        }

    def to_dict(self, include_files: bool = True) -> dict[str, Any]:
        payload = self.summary()
        payload["empty_files"] = self.empty_files
        payload["tiny_files"] = self.tiny_files
        payload["broken_symlinks"] = self.broken_symlinks
        payload["suspicious_extensions"] = self.suspicious_extensions
        payload["name_collisions"] = [item.to_dict() for item in self.name_collisions]
        payload["duplicate_groups"] = self.duplicate_groups
        payload["near_duplicate_groups"] = self.near_duplicate_groups
        if include_files:
            payload["files"] = [item.to_dict() for item in self.files]
        return payload

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AuditReport:
        collisions = [
            NameCollision(
                basename=str(item["basename"]),
                paths=list(item.get("paths", [])),
                sha256s=list(item.get("sha256s", [])),
            )
            for item in data.get("name_collisions", [])
        ]
        files = [
            FileRecord(
                path=str(item["path"]),
                size=int(item.get("size", 0)),
                sha256=str(item.get("sha256", "")),
                suffix=str(item.get("suffix", "<none>")),
                empty=bool(item.get("empty", item.get("size", 0) == 0)),
                is_symlink=bool(item.get("is_symlink", False)),
                broken_symlink=bool(item.get("broken_symlink", False)),
                phash=item.get("phash"),
                compressibility=item.get("compressibility"),
            )
            for item in data.get("files", [])
        ]
        return cls(
            root=str(data.get("root", "")),
            file_count=int(data.get("file_count", len(files))),
            total_bytes=int(data.get("total_bytes", 0)),
            empty_files=list(data.get("empty_files", [])),
            tiny_files=list(data.get("tiny_files", [])),
            broken_symlinks=list(data.get("broken_symlinks", [])),
            suspicious_extensions=list(data.get("suspicious_extensions", [])),
            name_collisions=collisions,
            duplicate_groups=[list(group) for group in data.get("duplicate_groups", [])],
            near_duplicate_groups=[list(group) for group in data.get("near_duplicate_groups", [])],
            extension_counts=dict(data.get("extension_counts", {})),
            size_histogram=dict(data.get("size_histogram", {})),
            largest_files=list(data.get("largest_files", [])),
            files=files,
            generated_at=str(data.get("generated_at", "")),
            perceptual_hash_enabled=bool(data.get("perceptual_hash_enabled", False)),
            compressibility_enabled=bool(data.get("compressibility_enabled", False)),
            tiny_threshold=int(data.get("tiny_threshold", 64)),
            exclude_patterns=list(data.get("exclude_patterns", [])),
        )
