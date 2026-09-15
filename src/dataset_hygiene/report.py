from __future__ import annotations

import html
import json
from pathlib import Path

from .models import AuditReport, DiffReport


def render_markdown(report: AuditReport) -> str:
    lines = [
        "# Dataset Hygiene Report",
        "",
        f"- **Root**: `{report.root}`",
        f"- **Generated at**: `{report.generated_at or 'n/a'}`",
        f"- **Files**: {report.file_count}",
        f"- **Total bytes**: {report.total_bytes:,}",
        f"- **Empty files**: {len(report.empty_files)}",
        f"- **Tiny files** (≤ {report.tiny_threshold} B): {len(report.tiny_files)}",
        f"- **Broken symlinks**: {len(report.broken_symlinks)}",
        f"- **Suspicious extensions**: {len(report.suspicious_extensions)}",
        f"- **Name collisions**: {len(report.name_collisions)}",
        f"- **Duplicate groups**: {len(report.duplicate_groups)}",
        f"- **Duplicate files**: {report.duplicate_file_count}",
        f"- **Near-duplicate groups**: {len(report.near_duplicate_groups)}",
        f"- **Perceptual hash**: `{str(report.perceptual_hash_enabled).lower()}`",
        f"- **Compressibility**: `{str(report.compressibility_enabled).lower()}`",
        f"- **Has issues**: `{str(report.has_issues).lower()}`",
        "",
        "## Extension histogram",
        "",
    ]
    if report.extension_counts:
        lines.append("| Extension | Count |")
        lines.append("| --- | ---: |")
        for suffix, count in report.extension_counts.items():
            lines.append(f"| `{suffix}` | {count} |")
    else:
        lines.append("_No files found._")

    lines.extend(["", "## Size histogram", ""])
    if report.size_histogram:
        lines.append("| Bucket | Count |")
        lines.append("| --- | ---: |")
        for bucket, count in report.size_histogram.items():
            lines.append(f"| `{bucket}` | {count} |")
    else:
        lines.append("_None._")

    lines.extend(["", "## Largest files", ""])
    if report.largest_files:
        lines.append("| Path | Size (bytes) |")
        lines.append("| --- | ---: |")
        for item in report.largest_files:
            lines.append(f"| `{item['path']}` | {item['size']:,} |")
    else:
        lines.append("_None._")

    def _section(title: str, paths: list[str]) -> None:
        lines.extend(["", f"## {title}", ""])
        if paths:
            lines.extend(f"- `{path}`" for path in paths)
        else:
            lines.append("_None._")

    _section("Empty files", report.empty_files)
    _section("Tiny files", report.tiny_files)
    _section("Broken symlinks", report.broken_symlinks)
    _section("Suspicious extensions", report.suspicious_extensions)

    lines.extend(["", "## Name collisions", ""])
    if report.name_collisions:
        for item in report.name_collisions:
            lines.append(f"### `{item.basename}`")
            lines.extend(f"- `{path}`" for path in item.paths)
            lines.append("")
    else:
        lines.append("_None._")
        lines.append("")

    lines.extend(["", "## Duplicate groups", ""])
    if report.duplicate_groups:
        for index, group in enumerate(report.duplicate_groups, start=1):
            lines.append(f"### Group {index} ({len(group)} files)")
            lines.extend(f"- `{path}`" for path in group)
            lines.append("")
    else:
        lines.append("_None._")
        lines.append("")

    lines.extend(["", "## Near-duplicate groups", ""])
    if report.near_duplicate_groups:
        for index, group in enumerate(report.near_duplicate_groups, start=1):
            lines.append(f"### Group {index} ({len(group)} files)")
            lines.extend(f"- `{path}`" for path in group)
            lines.append("")
    else:
        lines.append("_None._")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def render_diff_markdown(report: DiffReport) -> str:
    lines = [
        "# Dataset Hygiene Diff",
        "",
        f"- **Left**: `{report.left}`",
        f"- **Right**: `{report.right}`",
        f"- **Added**: {len(report.added)}",
        f"- **Removed**: {len(report.removed)}",
        f"- **Changed**: {len(report.changed)}",
        f"- **Unchanged**: {report.unchanged_count}",
        f"- **Has differences**: `{str(report.has_differences).lower()}`",
        "",
        "## Added",
        "",
    ]
    if report.added:
        lines.extend(f"- `{item.path}` ({item.new_sha256})" for item in report.added)
    else:
        lines.append("_None._")

    lines.extend(["", "## Removed", ""])
    if report.removed:
        lines.extend(f"- `{item.path}` ({item.old_sha256})" for item in report.removed)
    else:
        lines.append("_None._")

    lines.extend(["", "## Changed", ""])
    if report.changed:
        for item in report.changed:
            lines.append(
                f"- `{item.path}`: `{item.old_sha256}` → `{item.new_sha256}`"
            )
    else:
        lines.append("_None._")
    lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _html_escape(value: object) -> str:
    return html.escape(str(value), quote=True)


def render_html(report: AuditReport) -> str:
    def list_block(title: str, paths: list[str]) -> str:
        if not paths:
            return f"<section><h2>{_html_escape(title)}</h2><p class='muted'>None.</p></section>"
        items = "".join(f"<li><code>{_html_escape(path)}</code></li>" for path in paths)
        return f"<section><h2>{_html_escape(title)}</h2><ul>{items}</ul></section>"

    ext_rows = "".join(
        f"<tr><td><code>{_html_escape(suffix)}</code></td><td>{count}</td></tr>"
        for suffix, count in report.extension_counts.items()
    ) or "<tr><td colspan='2'>No files</td></tr>"
    size_rows = "".join(
        f"<tr><td><code>{_html_escape(bucket)}</code></td><td>{count}</td></tr>"
        for bucket, count in report.size_histogram.items()
    ) or "<tr><td colspan='2'>None</td></tr>"
    largest_rows = "".join(
        f"<tr><td><code>{_html_escape(item['path'])}</code></td><td>{item['size']:,}</td></tr>"
        for item in report.largest_files
    ) or "<tr><td colspan='2'>None</td></tr>"

    dup_html = ""
    if report.duplicate_groups:
        parts = []
        for index, group in enumerate(report.duplicate_groups, start=1):
            items = "".join(f"<li><code>{_html_escape(path)}</code></li>" for path in group)
            parts.append(f"<h3>Group {index} ({len(group)} files)</h3><ul>{items}</ul>")
        dup_html = "".join(parts)
    else:
        dup_html = "<p class='muted'>None.</p>"

    near_html = ""
    if report.near_duplicate_groups:
        parts = []
        for index, group in enumerate(report.near_duplicate_groups, start=1):
            items = "".join(f"<li><code>{_html_escape(path)}</code></li>" for path in group)
            parts.append(f"<h3>Group {index} ({len(group)} files)</h3><ul>{items}</ul>")
        near_html = "".join(parts)
    else:
        near_html = "<p class='muted'>None.</p>"

    collision_html = ""
    if report.name_collisions:
        parts = []
        for item in report.name_collisions:
            items = "".join(f"<li><code>{_html_escape(path)}</code></li>" for path in item.paths)
            parts.append(f"<h3><code>{_html_escape(item.basename)}</code></h3><ul>{items}</ul>")
        collision_html = "".join(parts)
    else:
        collision_html = "<p class='muted'>None.</p>"

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Dataset Hygiene Report</title>
  <style>
    :root {{
      --bg: #f6f3ee;
      --ink: #1c2430;
      --muted: #5b6675;
      --card: #fffdf9;
      --accent: #0f6a5c;
      --line: #d9d2c5;
    }}
    body {{
      margin: 0;
      font-family: "IBM Plex Sans", "Noto Sans SC", sans-serif;
      color: var(--ink);
      background:
        radial-gradient(circle at top left, #e7f2ef, transparent 40%),
        linear-gradient(180deg, #f8f5f0, var(--bg));
      line-height: 1.5;
    }}
    main {{
      max-width: 960px;
      margin: 0 auto;
      padding: 2.5rem 1.25rem 4rem;
    }}
    h1, h2, h3 {{ font-family: "IBM Plex Serif", "Noto Serif SC", serif; }}
    h1 {{ margin-bottom: 0.4rem; }}
    .meta {{ color: var(--muted); margin-bottom: 1.5rem; }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
      gap: 0.75rem;
      margin: 1.25rem 0 2rem;
    }}
    .stat {{
      background: var(--card);
      border: 1px solid var(--line);
      padding: 0.9rem 1rem;
    }}
    .stat strong {{ display: block; font-size: 1.35rem; color: var(--accent); }}
    table {{
      width: 100%;
      border-collapse: collapse;
      background: var(--card);
      border: 1px solid var(--line);
      margin-bottom: 1.5rem;
    }}
    th, td {{
      text-align: left;
      padding: 0.55rem 0.75rem;
      border-bottom: 1px solid var(--line);
      vertical-align: top;
    }}
    th {{ background: #f0ebe3; }}
    code {{ font-family: "IBM Plex Mono", Consolas, monospace; font-size: 0.92em; }}
    .muted {{ color: var(--muted); }}
    section {{ margin-bottom: 1.75rem; }}
  </style>
</head>
<body>
  <main>
    <h1>Dataset Hygiene Report</h1>
    <p class="meta">Root: <code>{_html_escape(report.root)}</code><br/>
    Generated: <code>{_html_escape(report.generated_at or 'n/a')}</code></p>
    <div class="grid">
      <div class="stat"><span>Files</span><strong>{report.file_count}</strong></div>
      <div class="stat"><span>Total bytes</span><strong>{report.total_bytes:,}</strong></div>
      <div class="stat"><span>Duplicates</span><strong>{len(report.duplicate_groups)}</strong></div>
      <div class="stat"><span>Issues</span><strong>{'yes' if report.has_issues else 'no'}</strong></div>
    </div>
    <section>
      <h2>Extension histogram</h2>
      <table><thead><tr><th>Extension</th><th>Count</th></tr></thead><tbody>{ext_rows}</tbody></table>
    </section>
    <section>
      <h2>Size histogram</h2>
      <table><thead><tr><th>Bucket</th><th>Count</th></tr></thead><tbody>{size_rows}</tbody></table>
    </section>
    <section>
      <h2>Largest files</h2>
      <table><thead><tr><th>Path</th><th>Size</th></tr></thead><tbody>{largest_rows}</tbody></table>
    </section>
    {list_block("Empty files", report.empty_files)}
    {list_block("Tiny files", report.tiny_files)}
    {list_block("Broken symlinks", report.broken_symlinks)}
    {list_block("Suspicious extensions", report.suspicious_extensions)}
    <section><h2>Name collisions</h2>{collision_html}</section>
    <section><h2>Duplicate groups</h2>{dup_html}</section>
    <section><h2>Near-duplicate groups</h2>{near_html}</section>
  </main>
</body>
</html>
"""


def write_reports(
    report: AuditReport,
    *,
    json_path: str | Path | None = None,
    markdown_path: str | Path | None = None,
    html_path: str | Path | None = None,
    include_files: bool = True,
) -> None:
    if json_path:
        path = Path(json_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(report.to_dict(include_files=include_files), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    if markdown_path:
        path = Path(markdown_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(render_markdown(report), encoding="utf-8")
    if html_path:
        path = Path(html_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(render_html(report), encoding="utf-8")


def write_diff_reports(
    report: DiffReport,
    *,
    json_path: str | Path | None = None,
    markdown_path: str | Path | None = None,
) -> None:
    if json_path:
        path = Path(json_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(report.to_dict(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    if markdown_path:
        path = Path(markdown_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(render_diff_markdown(report), encoding="utf-8")
