from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import AuditReport, DiffEntry, DiffReport
from .scan import audit_path


def _index_from_report(report: AuditReport) -> dict[str, dict[str, Any]]:
    if report.files:
        return {
            item.path: {"path": item.path, "size": item.size, "sha256": item.sha256}
            for item in report.files
        }
    # Fallback for summary-only reports is empty; callers should load full JSON.
    return {}


def _index_from_mapping(files: dict[str, dict[str, Any]] | list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    if isinstance(files, dict):
        return {
            path: {
                "path": path,
                "size": int(meta.get("size", 0)),
                "sha256": str(meta.get("sha256", "")),
            }
            for path, meta in files.items()
        }
    return {
        str(item["path"]): {
            "path": str(item["path"]),
            "size": int(item.get("size", 0)),
            "sha256": str(item.get("sha256", "")),
        }
        for item in files
    }


def load_audit_json(path: str | Path) -> AuditReport:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Audit JSON root must be an object")
    return AuditReport.from_dict(data)


def resolve_file_index(source: str | Path) -> tuple[str, dict[str, dict[str, Any]]]:
    """Accept a directory, audit JSON, or manifest JSON and return (label, path->meta)."""
    path = Path(source)
    if not path.exists():
        raise FileNotFoundError(f"Path does not exist: {path}")

    if path.is_dir():
        report = audit_path(path, include_file_details=True)
        return report.root, _index_from_report(report)

    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"JSON root must be an object: {path}")

    if "files" in data and isinstance(data["files"], list):
        label = str(data.get("root") or path)
        return label, _index_from_mapping(data["files"])

    raise ValueError(f"Unsupported JSON shape for diff input: {path}")


def diff_file_maps(
    left: dict[str, dict[str, Any]],
    right: dict[str, dict[str, Any]],
    *,
    left_label: str,
    right_label: str,
) -> DiffReport:
    left_paths = set(left)
    right_paths = set(right)

    added = [
        DiffEntry(
            path=path,
            new_sha256=right[path].get("sha256"),
            new_size=right[path].get("size"),
        )
        for path in sorted(right_paths - left_paths)
    ]
    removed = [
        DiffEntry(
            path=path,
            old_sha256=left[path].get("sha256"),
            old_size=left[path].get("size"),
        )
        for path in sorted(left_paths - right_paths)
    ]
    changed: list[DiffEntry] = []
    unchanged = 0
    for path in sorted(left_paths & right_paths):
        left_hash = left[path].get("sha256")
        right_hash = right[path].get("sha256")
        if left_hash != right_hash:
            changed.append(
                DiffEntry(
                    path=path,
                    old_sha256=left_hash,
                    new_sha256=right_hash,
                    old_size=left[path].get("size"),
                    new_size=right[path].get("size"),
                )
            )
        else:
            unchanged += 1

    return DiffReport(
        left=left_label,
        right=right_label,
        added=added,
        removed=removed,
        changed=changed,
        unchanged_count=unchanged,
    )


def diff_sources(left: str | Path, right: str | Path) -> DiffReport:
    left_label, left_index = resolve_file_index(left)
    right_label, right_index = resolve_file_index(right)
    return diff_file_maps(left_index, right_index, left_label=left_label, right_label=right_label)


def diff_reports(left: AuditReport, right: AuditReport) -> DiffReport:
    return diff_file_maps(
        _index_from_report(left),
        _index_from_report(right),
        left_label=left.root,
        right_label=right.root,
    )
