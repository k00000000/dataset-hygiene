"""dataset-hygiene: offline ML dataset auditing toolkit."""

from .diff import diff_reports, diff_sources
from .manifest import export_manifest, load_manifest, verify_manifest, write_manifest
from .models import AuditReport, DiffReport, FileRecord, Manifest
from .scan import audit_path

__all__ = [
    "AuditReport",
    "DiffReport",
    "FileRecord",
    "Manifest",
    "audit_path",
    "diff_reports",
    "diff_sources",
    "export_manifest",
    "load_manifest",
    "verify_manifest",
    "write_manifest",
    "__version__",
]
__version__ = "2.0.0"
