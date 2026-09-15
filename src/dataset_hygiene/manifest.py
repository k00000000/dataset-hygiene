from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .models import AuditReport, Manifest
from .scan import audit_path


MANIFEST_VERSION = 1


def export_manifest(
    root: str | Path,
    *,
    skip_hidden: bool = True,
    exclude_patterns: list[str] | None = None,
    report: AuditReport | None = None,
) -> Manifest:
    audit = report or audit_path(
        root,
        skip_hidden=skip_hidden,
        exclude_patterns=exclude_patterns,
        include_file_details=True,
        perceptual_hash=False,
        compute_compressibility=False,
    )
    files = [
        {
            "path": item.path,
            "size": item.size,
            "sha256": item.sha256,
            "suffix": item.suffix,
        }
        for item in audit.files
    ]
    return Manifest(
        version=MANIFEST_VERSION,
        root=audit.root,
        generated_at=audit.generated_at or datetime.now(timezone.utc).isoformat(),
        file_count=audit.file_count,
        total_bytes=audit.total_bytes,
        files=files,
    )


def write_manifest(manifest: Manifest, path: str | Path) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(manifest.to_dict(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def load_manifest(path: str | Path) -> Manifest:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Manifest root must be a JSON object")
    return Manifest.from_dict(payload)


def verify_manifest(
    manifest: Manifest,
    root: str | Path,
    *,
    skip_hidden: bool = True,
    exclude_patterns: list[str] | None = None,
) -> dict:
    """Compare a stored manifest against a live directory scan."""
    from .diff import diff_file_maps

    current = export_manifest(root, skip_hidden=skip_hidden, exclude_patterns=exclude_patterns)
    left = {item["path"]: item for item in manifest.files}
    right = {item["path"]: item for item in current.files}
    report = diff_file_maps(left, right, left_label=manifest.root or str(path_label(manifest)), right_label=str(Path(root).resolve()))
    return {
        "ok": not report.has_differences,
        "diff": report.to_dict(),
        "manifest_file_count": manifest.file_count,
        "current_file_count": current.file_count,
    }


def path_label(manifest: Manifest) -> str:
    return manifest.root or "<manifest>"
