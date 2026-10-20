"""TOML configuration loading and validation."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .errors import ConfigError


SUPPORTED_SOURCE_TYPES = frozenset({"json", "jsonl", "markdown"})


@dataclass(frozen=True, slots=True)
class SourceConfig:
    """One local source adapter declared in the TOML file."""

    name: str
    kind: str
    path: Path
    display_path: str
    enabled: bool = True
    items_path: str = "items"
    weight: float = 1.0
    freshness_hours: float = 24.0
    fields: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class AnalyzerConfig:
    """An optional external JSON-in/JSON-out analyzer command."""

    command: tuple[str, ...] = ()
    timeout_seconds: float = 120.0


@dataclass(frozen=True, slots=True)
class LoopConfig:
    """Deterministic ranking and retention controls."""

    freshness_hours: float = 24.0
    shortlist_limit: int = 10
    promotion_threshold: float = 0.55
    processed_ttl_hours: float = 336.0
    feedback_min_multiplier: float = 0.5
    feedback_max_multiplier: float = 1.5
    feedback_step: float = 0.05
    feedback_max_step: float = 0.2


@dataclass(frozen=True, slots=True)
class LimitsConfig:
    """Fail-closed resource limits for untrusted local source files."""

    max_source_bytes: int = 10_485_760
    max_rows: int = 5_000
    max_line_bytes: int = 262_144
    max_errors: int = 50
    max_engagement_depth: int = 4


@dataclass(frozen=True, slots=True)
class Settings:
    """Fully resolved application settings."""

    config_path: Path
    state_dir: Path
    timezone: str
    loop: LoopConfig
    limits: LimitsConfig
    sources: tuple[SourceConfig, ...]
    analyzer: AnalyzerConfig


DEFAULT_CONFIG = """# Signal Digest Loop — local, offline-first configuration
state_dir = ".signal-digest"
timezone = "UTC"

[loop]
freshness_hours = 24
shortlist_limit = 10
promotion_threshold = 0.55
processed_ttl_hours = 336
feedback_min_multiplier = 0.5
feedback_max_multiplier = 1.5
feedback_step = 0.05
feedback_max_step = 0.2

[limits]
max_source_bytes = 10485760
max_rows = 5000
max_line_bytes = 262144
max_errors = 50
max_engagement_depth = 4

[analyzer]
# command = ["python", "my_analyzer.py"]
timeout_seconds = 120

[[sources]]
name = "inbox"
type = "jsonl"
path = "signals.jsonl"
weight = 1.0
freshness_hours = 24
enabled = true

[sources.fields]
title = "title"
url = "url"
text = "text"
published_at = "published_at"
engagement = "engagement"
"""


def _positive_float(value: Any, label: str, default: float) -> float:
    try:
        parsed = float(default if value is None else value)
    except (TypeError, ValueError) as exc:
        raise ConfigError(f"{label} must be a number") from exc
    if parsed <= 0:
        raise ConfigError(f"{label} must be greater than zero")
    return parsed


def _bounded_float(value: Any, label: str, default: float, low: float, high: float) -> float:
    parsed = _positive_float(value, label, default)
    if not low <= parsed <= high:
        raise ConfigError(f"{label} must be between {low} and {high}")
    return parsed


def _bounded_int(value: Any, label: str, default: int, low: int, high: int) -> int:
    if value is not None and (isinstance(value, bool) or not isinstance(value, int)):
        raise ConfigError(f"{label} must be an integer")
    parsed = default if value is None else value
    if not low <= parsed <= high:
        raise ConfigError(f"{label} must be between {low} and {high}")
    return parsed


def _resolve(base: Path, raw: Any, label: str) -> Path:
    if not isinstance(raw, str) or not raw.strip():
        raise ConfigError(f"{label} must be a non-empty path")
    expanded = Path(raw).expanduser()
    return expanded if expanded.is_absolute() else (base / expanded).resolve()


def _command(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, list) and all(isinstance(part, str) for part in value):
        parts = tuple(value)
    else:
        raise ConfigError("analyzer.command must be an array of strings (shell syntax is forbidden)")
    if not parts or not parts[0].strip():
        raise ConfigError("analyzer.command cannot be empty")
    return parts


def load_settings(path: str | Path) -> Settings:
    """Read and validate a configuration file.

    Relative source and state paths are resolved against the directory that
    contains the TOML file, making a project directory safely relocatable.
    """

    config_path = Path(path).expanduser().resolve()
    try:
        with config_path.open("rb") as handle:
            payload = tomllib.load(handle)
    except FileNotFoundError as exc:
        raise ConfigError(f"configuration not found: {config_path}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"invalid TOML in {config_path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ConfigError("configuration root must be a TOML table")

    base = config_path.parent
    state_dir = _resolve(base, payload.get("state_dir", ".signal-digest"), "state_dir")
    timezone_name = payload.get("timezone", "UTC")
    if not isinstance(timezone_name, str) or not timezone_name.strip():
        raise ConfigError("timezone must be a non-empty IANA timezone name")

    loop_raw = payload.get("loop", {})
    if not isinstance(loop_raw, dict):
        raise ConfigError("loop must be a table")
    minimum = _bounded_float(
        loop_raw.get("feedback_min_multiplier"), "loop.feedback_min_multiplier", 0.5, 0.05, 10.0
    )
    maximum = _bounded_float(
        loop_raw.get("feedback_max_multiplier"), "loop.feedback_max_multiplier", 1.5, 0.05, 10.0
    )
    if minimum >= maximum:
        raise ConfigError("loop.feedback_min_multiplier must be below feedback_max_multiplier")
    try:
        shortlist_limit = int(loop_raw.get("shortlist_limit", 10))
    except (TypeError, ValueError) as exc:
        raise ConfigError("loop.shortlist_limit must be an integer") from exc
    if not 1 <= shortlist_limit <= 1000:
        raise ConfigError("loop.shortlist_limit must be between 1 and 1000")
    threshold = _bounded_float(
        loop_raw.get("promotion_threshold"), "loop.promotion_threshold", 0.55, 0.01, 1.0
    )
    loop = LoopConfig(
        freshness_hours=_positive_float(
            loop_raw.get("freshness_hours"), "loop.freshness_hours", 24.0
        ),
        shortlist_limit=shortlist_limit,
        promotion_threshold=threshold,
        processed_ttl_hours=_positive_float(
            loop_raw.get("processed_ttl_hours"), "loop.processed_ttl_hours", 336.0
        ),
        feedback_min_multiplier=minimum,
        feedback_max_multiplier=maximum,
        feedback_step=_bounded_float(
            loop_raw.get("feedback_step"), "loop.feedback_step", 0.05, 0.001, 1.0
        ),
        feedback_max_step=_bounded_float(
            loop_raw.get("feedback_max_step"), "loop.feedback_max_step", 0.2, 0.001, 1.0
        ),
    )
    if loop.feedback_step > loop.feedback_max_step:
        raise ConfigError("loop.feedback_step cannot exceed feedback_max_step")

    limits_raw = payload.get("limits", {})
    if not isinstance(limits_raw, dict):
        raise ConfigError("limits must be a table")
    limits = LimitsConfig(
        max_source_bytes=_bounded_int(
            limits_raw.get("max_source_bytes"),
            "limits.max_source_bytes",
            10_485_760,
            1_024,
            1_073_741_824,
        ),
        max_rows=_bounded_int(
            limits_raw.get("max_rows"), "limits.max_rows", 5_000, 1, 1_000_000
        ),
        max_line_bytes=_bounded_int(
            limits_raw.get("max_line_bytes"),
            "limits.max_line_bytes",
            262_144,
            128,
            16_777_216,
        ),
        max_errors=_bounded_int(
            limits_raw.get("max_errors"), "limits.max_errors", 50, 1, 100_000
        ),
        max_engagement_depth=_bounded_int(
            limits_raw.get("max_engagement_depth"),
            "limits.max_engagement_depth",
            4,
            1,
            32,
        ),
    )
    raw_sources = payload.get("sources", [])
    if not isinstance(raw_sources, list) or not raw_sources:
        raise ConfigError("at least one [[sources]] table is required")
    sources: list[SourceConfig] = []
    seen_names: set[str] = set()
    for index, raw in enumerate(raw_sources):
        label = f"sources[{index}]"
        if not isinstance(raw, dict):
            raise ConfigError(f"{label} must be a table")
        name = raw.get("name")
        if not isinstance(name, str) or not name.strip():
            raise ConfigError(f"{label}.name must be non-empty")
        if name in seen_names:
            raise ConfigError(f"duplicate source name: {name}")
        seen_names.add(name)
        kind = raw.get("type")
        if kind not in SUPPORTED_SOURCE_TYPES:
            choices = ", ".join(sorted(SUPPORTED_SOURCE_TYPES))
            raise ConfigError(f"{label}.type must be one of: {choices}")
        fields_raw = raw.get("fields", {})
        if not isinstance(fields_raw, dict) or not all(
            isinstance(key, str) and isinstance(value, str) for key, value in fields_raw.items()
        ):
            raise ConfigError(f"{label}.fields must map strings to strings")
        fields = {
            "title": str(fields_raw.get("title", raw.get("title_field", "title"))),
            "url": str(fields_raw.get("url", raw.get("url_field", "url"))),
            "text": str(fields_raw.get("text", raw.get("text_field", "text"))),
            "published_at": str(
                fields_raw.get("published_at", raw.get("published_at_field", "published_at"))
            ),
            "engagement": str(
                fields_raw.get("engagement", raw.get("engagement_field", "engagement"))
            ),
        }
        raw_path = raw.get("path")
        resolved_path = _resolve(base, raw_path, f"{label}.path")
        assert isinstance(raw_path, str)
        display_path = Path(raw_path).name if Path(raw_path).is_absolute() else str(Path(raw_path))
        sources.append(
            SourceConfig(
                name=name,
                kind=kind,
                path=resolved_path,
                display_path=display_path,
                enabled=bool(raw.get("enabled", True)),
                items_path=str(raw.get("items_path", "items")),
                weight=_bounded_float(raw.get("weight"), f"{label}.weight", 1.0, 0.05, 10.0),
                freshness_hours=_positive_float(
                    raw.get("freshness_hours"), f"{label}.freshness_hours", loop.freshness_hours
                ),
                fields=fields,
            )
        )

    analyzer_raw = payload.get("analyzer", {})
    if not isinstance(analyzer_raw, dict):
        raise ConfigError("analyzer must be a table")
    analyzer = AnalyzerConfig(
        command=_command(analyzer_raw.get("command")),
        timeout_seconds=_positive_float(
            analyzer_raw.get("timeout_seconds"), "analyzer.timeout_seconds", 120.0
        ),
    )
    return Settings(
        config_path=config_path,
        state_dir=state_dir,
        timezone=timezone_name.strip(),
        loop=loop,
        limits=limits,
        sources=tuple(sources),
        analyzer=analyzer,
    )
