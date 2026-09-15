from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any


DEFAULT_SUSPICIOUS_EXTENSIONS = (
    ".exe",
    ".bat",
    ".cmd",
    ".com",
    ".scr",
    ".dll",
    ".msi",
    ".ps1",
    ".vbs",
    ".js",
    ".jar",
    ".apk",
    ".dmg",
    ".sh",
)


@dataclass
class HygieneConfig:
    include_hidden: bool = False
    largest: int = 10
    tiny_threshold: int = 64
    exclude: list[str] = field(default_factory=list)
    suspicious_extensions: list[str] = field(
        default_factory=lambda: list(DEFAULT_SUSPICIOUS_EXTENSIONS)
    )
    perceptual_hash: bool = False
    compute_compressibility: bool = False
    fail_on_issues: bool = False
    summary_only: bool = False
    top_extensions: int = 20

    def merged_with(self, overrides: dict[str, Any]) -> HygieneConfig:
        data = asdict(self)
        for key, value in overrides.items():
            if key not in data or value is None:
                continue
            data[key] = value
        return HygieneConfig(**data)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _import_tomllib():  # type: ignore[no-untyped-def]
    try:
        import tomllib

        return tomllib
    except ModuleNotFoundError:  # pragma: no cover - exercised on 3.10 without tomli
        try:
            import tomli as tomllib  # type: ignore[no-redef]

            return tomllib
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "TOML config requires Python 3.11+ (tomllib) or the optional 'tomli' package"
            ) from exc


def discover_config_path(start: Path | None = None) -> Path | None:
    candidates: list[Path] = []
    if start is not None:
        candidates.append(start / ".dataset-hygiene.toml")
    candidates.append(Path.cwd() / ".dataset-hygiene.toml")
    for path in candidates:
        if path.is_file():
            return path
    return None


def load_toml_file(path: Path) -> dict[str, Any]:
    tomllib = _import_tomllib()
    with path.open("rb") as handle:
        data = tomllib.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"Config root must be a table: {path}")
    return data


def config_from_mapping(data: dict[str, Any]) -> HygieneConfig:
    allowed = {item.name for item in fields(HygieneConfig)}
    unknown = sorted(set(data) - allowed)
    if unknown:
        raise ValueError(f"Unknown config keys: {', '.join(unknown)}")

    kwargs: dict[str, Any] = {}
    for key in allowed:
        if key not in data:
            continue
        value = data[key]
        if key in {"exclude", "suspicious_extensions"}:
            if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
                raise ValueError(f"Config key '{key}' must be a list of strings")
            kwargs[key] = list(value)
        else:
            kwargs[key] = value
    return HygieneConfig(**kwargs)


def load_config(path: str | Path | None = None, *, search_root: Path | None = None) -> HygieneConfig:
    if path is not None:
        config_path = Path(path)
        if not config_path.is_file():
            raise FileNotFoundError(f"Config file not found: {config_path}")
    else:
        config_path = discover_config_path(search_root)
        if config_path is None:
            return HygieneConfig()
    return config_from_mapping(load_toml_file(config_path))
