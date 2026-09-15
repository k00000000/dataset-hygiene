from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .config import HygieneConfig, load_config
from .diff import diff_sources
from .manifest import export_manifest, load_manifest, verify_manifest, write_manifest
from .report import (
    render_diff_markdown,
    render_markdown,
    write_diff_reports,
    write_reports,
)
from .scan import audit_path


def _add_common_scan_flags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--config", help="Path to .dataset-hygiene.toml")
    parser.add_argument("--include-hidden", action="store_true", help="Include hidden files/dirs")
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        metavar="GLOB",
        help="Exclude glob pattern (repeatable)",
    )
    parser.add_argument("--largest", type=int, default=None, help="How many largest files to list")
    parser.add_argument(
        "--tiny-threshold",
        type=int,
        default=None,
        help="Flag non-empty files at or below this many bytes",
    )
    parser.add_argument(
        "--perceptual-hash",
        action="store_true",
        help="Enable optional image near-duplicate detection (requires Pillow)",
    )
    parser.add_argument(
        "--compressibility",
        action="store_true",
        help="Sample files for rough zlib compressibility scores",
    )
    parser.add_argument(
        "--summary-only",
        action="store_true",
        help="Do not embed per-file rows in JSON output",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dataset-hygiene",
        description="Offline ML dataset auditor with audit / diff / manifest subcommands.",
    )
    parser.add_argument("--version", action="store_true", help="Print version and exit")
    sub = parser.add_subparsers(dest="command")

    audit = sub.add_parser("audit", help="Scan a dataset directory and emit reports")
    audit.add_argument("root", help="Dataset root directory to audit")
    _add_common_scan_flags(audit)
    audit.add_argument("--json", dest="json_path", help="Write machine-readable JSON report")
    audit.add_argument("--markdown", dest="markdown_path", help="Write human-readable Markdown report")
    audit.add_argument("--html", dest="html_path", help="Write self-contained HTML report")
    audit.add_argument(
        "--fail-on-issues",
        action="store_true",
        help="Exit with code 2 when hygiene issues are found",
    )

    diff = sub.add_parser("diff", help="Compare two directories or two audit/manifest JSON files")
    diff.add_argument("left", help="Left directory or JSON report/manifest")
    diff.add_argument("right", help="Right directory or JSON report/manifest")
    diff.add_argument("--json", dest="json_path", help="Write JSON diff")
    diff.add_argument("--markdown", dest="markdown_path", help="Write Markdown diff")
    diff.add_argument(
        "--fail-on-diff",
        action="store_true",
        help="Exit with code 2 when differences exist",
    )

    manifest = sub.add_parser("manifest", help="Export or verify reproducible file manifests")
    manifest_sub = manifest.add_subparsers(dest="manifest_command", required=True)

    export_cmd = manifest_sub.add_parser("export", help="Export a JSON manifest from a directory")
    export_cmd.add_argument("root", help="Dataset root directory")
    export_cmd.add_argument("-o", "--output", required=True, help="Output manifest JSON path")
    _add_common_scan_flags(export_cmd)

    verify_cmd = manifest_sub.add_parser("verify", help="Verify a directory against a manifest")
    verify_cmd.add_argument("manifest", help="Manifest JSON path")
    verify_cmd.add_argument("root", help="Dataset root directory to verify")
    verify_cmd.add_argument("--config", help="Path to .dataset-hygiene.toml")
    verify_cmd.add_argument("--include-hidden", action="store_true", help="Include hidden files/dirs")
    verify_cmd.add_argument(
        "--exclude",
        action="append",
        default=[],
        metavar="GLOB",
        help="Exclude glob pattern (repeatable)",
    )
    verify_cmd.add_argument("--json", dest="json_path", help="Write verification JSON result")
    verify_cmd.add_argument(
        "--fail-on-diff",
        action="store_true",
        help="Exit with code 2 when verification fails",
    )

    return parser


def _resolve_config(args: argparse.Namespace, root: str | Path | None = None) -> HygieneConfig:
    search_root = Path(root) if root is not None else None
    config = load_config(getattr(args, "config", None), search_root=search_root)

    overrides: dict = {}
    if getattr(args, "include_hidden", False):
        overrides["include_hidden"] = True
    if getattr(args, "exclude", None):
        overrides["exclude"] = list(dict.fromkeys([*config.exclude, *args.exclude]))
    if getattr(args, "largest", None) is not None:
        overrides["largest"] = args.largest
    if getattr(args, "tiny_threshold", None) is not None:
        overrides["tiny_threshold"] = args.tiny_threshold
    if getattr(args, "perceptual_hash", False):
        overrides["perceptual_hash"] = True
    if getattr(args, "compressibility", False):
        overrides["compute_compressibility"] = True
    if getattr(args, "summary_only", False):
        overrides["summary_only"] = True
    if getattr(args, "fail_on_issues", False):
        overrides["fail_on_issues"] = True
    return config.merged_with(overrides)


def _cmd_audit(args: argparse.Namespace) -> int:
    config = _resolve_config(args, root=args.root)
    report = audit_path(args.root, config=config)
    write_reports(
        report,
        json_path=args.json_path,
        markdown_path=args.markdown_path,
        html_path=args.html_path,
        include_files=not config.summary_only,
    )

    if args.markdown_path or args.json_path or args.html_path:
        print(json.dumps(report.summary(), ensure_ascii=False, indent=2))
    else:
        print(render_markdown(report), end="")

    if config.fail_on_issues and report.has_issues:
        return 2
    return 0


def _cmd_diff(args: argparse.Namespace) -> int:
    report = diff_sources(args.left, args.right)
    write_diff_reports(report, json_path=args.json_path, markdown_path=args.markdown_path)
    if args.markdown_path or args.json_path:
        print(json.dumps(report.summary(), ensure_ascii=False, indent=2))
    else:
        print(render_diff_markdown(report), end="")
    if args.fail_on_diff and report.has_differences:
        return 2
    return 0


def _cmd_manifest_export(args: argparse.Namespace) -> int:
    config = _resolve_config(args, root=args.root)
    report = audit_path(args.root, config=config.merged_with({"summary_only": False}))
    manifest = export_manifest(args.root, report=report)
    write_manifest(manifest, args.output)
    print(
        json.dumps(
            {
                "output": str(Path(args.output)),
                "file_count": manifest.file_count,
                "total_bytes": manifest.total_bytes,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def _cmd_manifest_verify(args: argparse.Namespace) -> int:
    config = _resolve_config(args, root=args.root)
    manifest = load_manifest(args.manifest)
    result = verify_manifest(
        manifest,
        args.root,
        skip_hidden=not config.include_hidden,
        exclude_patterns=config.exclude,
    )
    if args.json_path:
        path = Path(args.json_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("ok", "manifest_file_count", "current_file_count")}, indent=2))
    if args.fail_on_diff and not result["ok"]:
        return 2
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.version:
        print(__version__)
        return 0

    if not args.command:
        parser.error("a subcommand is required: audit | diff | manifest (or use --version)")

    try:
        if args.command == "audit":
            return _cmd_audit(args)
        if args.command == "diff":
            return _cmd_diff(args)
        if args.command == "manifest":
            if args.manifest_command == "export":
                return _cmd_manifest_export(args)
            if args.manifest_command == "verify":
                return _cmd_manifest_verify(args)
    except (FileNotFoundError, NotADirectoryError, ValueError, RuntimeError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    parser.error(f"unknown command: {args.command}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
