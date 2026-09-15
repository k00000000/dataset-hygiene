from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from dataset_hygiene.cli import main
from dataset_hygiene.config import HygieneConfig, config_from_mapping, load_config
from dataset_hygiene.diff import diff_sources
from dataset_hygiene.manifest import export_manifest, load_manifest, verify_manifest, write_manifest
from dataset_hygiene.phash import group_near_duplicates, hamming_distance, pillow_available
from dataset_hygiene.scan import audit_path
from dataset_hygiene.stats import build_size_histogram, rough_compressibility, size_bucket
from dataset_hygiene.suspicion import find_name_collisions


@pytest.fixture()
def sample_dataset(tmp_path: Path) -> Path:
    root = tmp_path / "dataset"
    (root / "images").mkdir(parents=True)
    (root / "labels").mkdir(parents=True)
    (root / "scratch").mkdir(parents=True)
    (root / "images" / "a.txt").write_text("hello-dataset", encoding="utf-8")
    (root / "images" / "b.txt").write_text("hello-dataset", encoding="utf-8")
    (root / "labels" / "a.txt").write_text("unique-label", encoding="utf-8")
    (root / "labels" / "tiny.txt").write_text("x", encoding="utf-8")
    (root / "empty.bin").write_bytes(b"")
    (root / "tool.exe").write_bytes(b"MZ-fake")
    (root / "scratch" / "junk.tmp").write_text("tmp", encoding="utf-8")
    (root / "ignore.tmp").write_text("tmp-root", encoding="utf-8")
    (root / ".hidden").write_text("secret", encoding="utf-8")
    (root / ".git" / "config").parent.mkdir(parents=True, exist_ok=True)
    (root / ".git" / "config").write_text("should-skip", encoding="utf-8")
    return root


def test_audit_detects_duplicates_empty_and_suspicion(sample_dataset: Path) -> None:
    report = audit_path(sample_dataset, tiny_threshold=8, exclude_patterns=["*.tmp", "scratch/**"])
    assert report.file_count == 6
    assert report.empty_files == ["empty.bin"]
    assert "labels/tiny.txt" in report.tiny_files
    assert "tool.exe" in report.suspicious_extensions
    assert len(report.duplicate_groups) == 1
    assert set(report.duplicate_groups[0]) == {"images/a.txt", "images/b.txt"}
    assert any(item.basename == "a.txt" for item in report.name_collisions)
    assert report.size_histogram
    assert report.has_issues is True
    assert "ignore.tmp" not in {item.path for item in report.files}


def test_cli_audit_writes_reports(sample_dataset: Path, tmp_path: Path) -> None:
    json_path = tmp_path / "report.json"
    md_path = tmp_path / "report.md"
    html_path = tmp_path / "report.html"
    code = main(
        [
            "audit",
            str(sample_dataset),
            "--json",
            str(json_path),
            "--markdown",
            str(md_path),
            "--html",
            str(html_path),
            "--exclude",
            "*.tmp",
            "--exclude",
            "scratch/**",
            "--summary-only",
            "--fail-on-issues",
        ]
    )
    assert code == 2
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["duplicate_group_count"] == 1
    assert "files" not in payload
    md = md_path.read_text(encoding="utf-8")
    html = html_path.read_text(encoding="utf-8")
    assert "Dataset Hygiene Report" in md
    assert "<!DOCTYPE html>" in html
    assert "Size histogram" in html or "Size histogram" in md


def test_version() -> None:
    assert main(["--version"]) == 0


def test_manifest_export_and_verify(sample_dataset: Path, tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    assert main(["manifest", "export", str(sample_dataset), "-o", str(manifest_path), "--exclude", "*.tmp"]) == 0
    manifest = load_manifest(manifest_path)
    assert manifest.file_count >= 4
    result = verify_manifest(manifest, sample_dataset, exclude_patterns=["*.tmp"])
    assert result["ok"] is True

    (sample_dataset / "labels" / "a.txt").write_text("changed", encoding="utf-8")
    code = main(
        [
            "manifest",
            "verify",
            str(manifest_path),
            str(sample_dataset),
            "--exclude",
            "*.tmp",
            "--fail-on-diff",
        ]
    )
    assert code == 2


def test_diff_directories_and_json(sample_dataset: Path, tmp_path: Path) -> None:
    left = tmp_path / "left"
    right = tmp_path / "right"
    left.mkdir()
    right.mkdir()
    (left / "a.txt").write_text("one", encoding="utf-8")
    (left / "b.txt").write_text("two", encoding="utf-8")
    (right / "a.txt").write_text("ONE", encoding="utf-8")
    (right / "c.txt").write_text("three", encoding="utf-8")

    report = diff_sources(left, right)
    assert [item.path for item in report.added] == ["c.txt"]
    assert [item.path for item in report.removed] == ["b.txt"]
    assert [item.path for item in report.changed] == ["a.txt"]

    left_json = tmp_path / "left.json"
    right_json = tmp_path / "right.json"
    write_manifest(export_manifest(left), left_json)
    write_manifest(export_manifest(right), right_json)
    code = main(["diff", str(left_json), str(right_json), "--fail-on-diff"])
    assert code == 2


def test_config_file_loading(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    if sys.version_info < (3, 11):
        pytest.importorskip("tomli")

    cfg = tmp_path / ".dataset-hygiene.toml"
    cfg.write_text(
        "\n".join(
            [
                "include_hidden = true",
                "tiny_threshold = 3",
                'exclude = ["*.tmp"]',
                "fail_on_issues = true",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    loaded = load_config()
    assert loaded.include_hidden is True
    assert loaded.tiny_threshold == 3
    assert loaded.exclude == ["*.tmp"]
    assert loaded.fail_on_issues is True

    mapped = config_from_mapping({"largest": 5, "perceptual_hash": True})
    assert mapped.largest == 5
    assert mapped.perceptual_hash is True


def test_cli_uses_config(tmp_path: Path) -> None:
    if sys.version_info < (3, 11):
        pytest.importorskip("tomli")

    root = tmp_path / "data"
    root.mkdir()
    (root / "keep.txt").write_text("keep", encoding="utf-8")
    (root / "drop.tmp").write_text("drop", encoding="utf-8")
    cfg = tmp_path / "custom.toml"
    cfg.write_text('exclude = ["*.tmp"]\ntiny_threshold = 1\n', encoding="utf-8")
    json_path = tmp_path / "out.json"
    code = main(["audit", str(root), "--config", str(cfg), "--json", str(json_path)])
    assert code == 0
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["file_count"] == 1
    assert payload["exclude_patterns"] == ["*.tmp"]


def test_compressibility_and_histogram() -> None:
    assert size_bucket(0) == "0B"
    assert size_bucket(100) == "1B-1KiB"
    assert size_bucket(2_000_000) == "1MiB-16MiB"
    score = rough_compressibility(b"aaaaaaaaaa" * 100)
    assert score is not None and score > 0.5
    assert rough_compressibility(b"") is None

    from dataset_hygiene.models import FileRecord

    records = [
        FileRecord(path="a", size=0, sha256="0", suffix=".bin", empty=True),
        FileRecord(path="b", size=10, sha256="1", suffix=".txt", empty=False),
        FileRecord(path="c", size=10_000, sha256="2", suffix=".txt", empty=False),
    ]
    hist = build_size_histogram(records)
    assert hist["0B"] == 1
    assert hist["1B-1KiB"] == 1


def test_name_collisions_and_phash_helpers() -> None:
    from dataset_hygiene.models import FileRecord

    records = [
        FileRecord(path="x/a.txt", size=1, sha256="aa", suffix=".txt", empty=False),
        FileRecord(path="y/a.txt", size=2, sha256="bb", suffix=".txt", empty=False),
        FileRecord(path="z/a.txt", size=1, sha256="aa", suffix=".txt", empty=False),
    ]
    collisions = find_name_collisions(records)
    assert len(collisions) == 1
    assert collisions[0].basename == "a.txt"

    assert hamming_distance("00", "0f") == 4
    groups = group_near_duplicates({"a.png": "0000", "b.png": "0001", "c.png": "ffff"}, max_distance=2)
    assert groups and set(groups[0]) == {"a.png", "b.png"}


@pytest.mark.skipif(not pillow_available(), reason="Pillow not installed")
def test_perceptual_hash_near_duplicates(tmp_path: Path) -> None:
    from PIL import Image

    root = tmp_path / "imgs"
    root.mkdir()
    img1 = Image.new("RGB", (32, 32), color=(200, 10, 10))
    img2 = Image.new("RGB", (32, 32), color=(198, 12, 12))
    img3 = Image.new("RGB", (32, 32), color=(10, 200, 10))
    img1.save(root / "a.png")
    img2.save(root / "b.png")
    img3.save(root / "c.png")

    report = audit_path(root, perceptual_hash=True)
    assert report.perceptual_hash_enabled is True
    assert report.near_duplicate_groups
    flat = {path for group in report.near_duplicate_groups for path in group}
    assert "a.png" in flat and "b.png" in flat


def test_broken_symlink_detection(tmp_path: Path) -> None:
    root = tmp_path / "sym"
    root.mkdir()
    (root / "real.txt").write_text("ok", encoding="utf-8")
    link = root / "broken.txt"
    try:
        link.symlink_to(root / "missing-target.txt")
    except OSError:
        pytest.skip("symlinks not permitted on this platform/user")

    report = audit_path(root)
    assert "broken.txt" in report.broken_symlinks
    assert report.has_issues is True


def test_audit_path_errors(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        audit_path(tmp_path / "nope")
    file_path = tmp_path / "file.txt"
    file_path.write_text("x", encoding="utf-8")
    with pytest.raises(NotADirectoryError):
        audit_path(file_path)


def test_unknown_config_key() -> None:
    with pytest.raises(ValueError):
        config_from_mapping({"not_a_key": 1})


def test_hygiene_config_merge() -> None:
    base = HygieneConfig(exclude=["*.tmp"], tiny_threshold=10)
    merged = base.merged_with({"tiny_threshold": 20, "perceptual_hash": True, "ignore": 1})
    assert merged.tiny_threshold == 20
    assert merged.perceptual_hash is True
    assert merged.exclude == ["*.tmp"]
