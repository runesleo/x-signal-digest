"""Local JSON, JSONL, and Markdown source adapters."""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from .config import LimitsConfig, SourceConfig
from .storage import content_hash


HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
MARKDOWN_LINK = re.compile(r"\[([^\]]+)\]\((https?://[^)\s]+)\)")
PLAIN_URL = re.compile(r"https?://[^\s)>\]]+")
TRACKING_KEY = re.compile(r"^(?:utm_.+|fbclid|gclid|mc_cid|mc_eid|ref_src)$", re.I)


@dataclass(slots=True)
class LoadedSource:
    """Normalized candidates plus observable adapter health."""

    candidates: list[dict[str, Any]]
    health: dict[str, Any]


class SourceLimitError(ValueError):
    """A source exceeded a configured resource budget."""

    def __init__(self, limit: str, message: str, *, rows_examined: int = 0) -> None:
        super().__init__(message)
        self.limit = limit
        self.rows_examined = rows_examined


def iso_utc(value: datetime) -> str:
    """Format an aware datetime as ISO-8601 UTC."""

    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_datetime(value: Any) -> datetime | None:
    """Parse common ISO-8601 and RFC-2822 timestamps."""

    if not isinstance(value, str) or not value.strip():
        return None
    raw = value.strip()
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except (ValueError, OverflowError):
        try:
            parsed = parsedate_to_datetime(raw)
        except (TypeError, ValueError, OverflowError):
            return None
    if parsed.tzinfo is None:
        return None
    try:
        return parsed.astimezone(timezone.utc)
    except (OverflowError, ValueError):
        return None


def _safe_error(exc: BaseException) -> str:
    """Describe a read error without echoing filesystem paths."""

    if isinstance(exc, OSError):
        return f"{type(exc).__name__}: {exc.strerror or 'unreadable source'}"
    return str(exc)


def canonical_url(value: Any) -> str:
    """Normalize a web URL and remove common tracking parameters."""

    if not isinstance(value, str) or not value.strip():
        return ""
    raw = value.strip().rstrip(".,;!?)\"'")
    try:
        parts = urlsplit(raw)
        if parts.scheme.lower() not in {"http", "https"} or not parts.hostname:
            return ""
        scheme = parts.scheme.lower()
        host = parts.hostname.lower()
        try:
            port = parts.port
        except ValueError:
            return ""
        netloc = host
        if port and (scheme, port) not in {("http", 80), ("https", 443)}:
            netloc = f"{host}:{port}"
        path = re.sub(r"/{2,}", "/", parts.path or "/")
        if path != "/":
            path = path.rstrip("/")
        query = urlencode(
            sorted(
                (key, item)
                for key, item in parse_qsl(parts.query, keep_blank_values=True)
                if not TRACKING_KEY.match(key)
            )
        )
        return urlunsplit((scheme, netloc, path, query, ""))
    except (TypeError, ValueError):
        return ""


def _clean_text(value: Any, limit: int = 8000) -> str:
    text = " ".join(str(value or "").split())
    return text[:limit]


def _dot_get(payload: Any, dotted_path: str, default: Any = None) -> Any:
    if not dotted_path:
        return payload
    current = payload
    for part in dotted_path.split("."):
        if not isinstance(current, dict) or part not in current:
            return default
        current = current[part]
    return current


def _read_markdown(path: Path, max_rows: int) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8")
    sections: list[tuple[str, list[str]]] = []
    title = path.stem.replace("-", " ").replace("_", " ").strip()
    body: list[str] = []
    for line in text.splitlines():
        match = HEADING.match(line)
        if match:
            if body or sections:
                sections.append((title, body))
                if len(sections) > max_rows:
                    raise SourceLimitError(
                        "max_rows",
                        f"max_rows exceeded ({max_rows})",
                        rows_examined=len(sections),
                    )
            title = match.group(2).strip()
            body = []
        else:
            body.append(line)
    if body or not sections:
        sections.append((title, body))
    if len(sections) > max_rows:
        raise SourceLimitError(
            "max_rows", f"max_rows exceeded ({max_rows})", rows_examined=len(sections)
        )

    modified = iso_utc(datetime.fromtimestamp(path.stat().st_mtime, timezone.utc))
    items: list[dict[str, Any]] = []
    for section_title, lines in sections:
        section_text = "\n".join(lines).strip()
        links = MARKDOWN_LINK.findall(section_text)
        urls = [url for _, url in links] or PLAIN_URL.findall(section_text)
        items.append(
            {
                "title": section_title,
                "text": section_text,
                "url": urls[0] if urls else "",
                "published_at": modified,
            }
        )
    return items


def _read_rows(
    source: SourceConfig,
    resolved_path: Path,
    limits: LimitsConfig,
    row_budget: int,
) -> tuple[list[Any], list[str], int]:
    errors: list[str] = []
    max_rows = min(limits.max_rows, row_budget)
    if max_rows <= 0:
        raise SourceLimitError("max_rows", "global max_rows budget exhausted")
    if source.kind == "markdown":
        rows = _read_markdown(resolved_path, max_rows)
        return rows, errors, len(rows)
    if source.kind == "jsonl":
        rows: list[Any] = []
        rows_examined = 0
        errors_seen = 0
        with resolved_path.open("rb") as handle:
            line_number = 0
            while True:
                raw_line = handle.readline(limits.max_line_bytes + 1)
                if not raw_line:
                    break
                line_number += 1
                if len(raw_line) > limits.max_line_bytes:
                    raise SourceLimitError(
                        "max_line_bytes",
                        f"line {line_number} exceeds max_line_bytes ({limits.max_line_bytes})",
                        rows_examined=rows_examined,
                    )
                if not raw_line.strip():
                    continue
                rows_examined += 1
                if rows_examined > max_rows:
                    raise SourceLimitError(
                        "max_rows",
                        f"max_rows exceeded ({max_rows})",
                        rows_examined=rows_examined,
                    )
                try:
                    line = raw_line.decode("utf-8")
                    rows.append(json.loads(line))
                except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                    errors_seen += 1
                    if errors_seen > limits.max_errors:
                        raise SourceLimitError(
                            "max_errors",
                            f"max_errors exceeded ({limits.max_errors})",
                            rows_examined=rows_examined,
                        ) from exc
                    errors.append(f"line {line_number}: {getattr(exc, 'msg', str(exc))}")
        return rows, errors, rows_examined

    with resolved_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if isinstance(payload, list):
        rows = payload
    else:
        rows = _dot_get(payload, source.items_path, [])
    if not isinstance(rows, list):
        raise ValueError(f"items_path {source.items_path!r} does not resolve to a list")
    if len(rows) > max_rows:
        raise SourceLimitError(
            "max_rows", f"max_rows exceeded ({max_rows})", rows_examined=max_rows + 1
        )
    return rows, errors, len(rows)


def _number(value: Any, max_depth: int, depth: int = 0) -> float:
    if isinstance(value, bool):
        return 0.0
    if isinstance(value, dict):
        if depth >= max_depth:
            return 0.0
        return sum(_number(item, max_depth, depth + 1) for item in value.values())
    if isinstance(value, (list, tuple)):
        if depth >= max_depth:
            return 0.0
        return sum(_number(item, max_depth, depth + 1) for item in value)
    try:
        parsed = float(value)
    except (TypeError, ValueError, OverflowError):
        return 0.0
    return max(0.0, parsed) if math.isfinite(parsed) else 0.0


def _normalize(
    row: dict[str, Any],
    source: SourceConfig,
    index: int,
    observed_at: datetime,
    max_engagement_depth: int,
) -> dict[str, Any] | None:
    fields = source.fields
    title = _clean_text(_dot_get(row, fields["title"], ""), 500)
    text = _clean_text(_dot_get(row, fields["text"], ""))
    url = canonical_url(_dot_get(row, fields["url"], ""))
    if not title:
        title = text[:160] or url
    if not title and not text and not url:
        return None
    published = parse_datetime(_dot_get(row, fields["published_at"]))
    identity = url or " ".join(f"{title} {text[:1200]}".lower().split())
    fingerprint = content_hash({"identity": identity}, 32)
    return {
        "id": f"sig_{fingerprint[:24]}",
        "fingerprint": fingerprint,
        "source": source.name,
        "source_type": source.kind,
        "title": title,
        "url": url,
        "text": text,
        "published_at": iso_utc(published) if published else None,
        "observed_at": iso_utc(observed_at),
        "engagement": _number(
            _dot_get(row, fields["engagement"], 0), max_engagement_depth
        ),
        "provenance": {"path": source.display_path, "index": index},
    }


def _age_hours(value: datetime, now: datetime) -> float:
    return max(0.0, (now - value).total_seconds() / 3600.0)


def load_source(
    source: SourceConfig,
    now: datetime,
    local_date: str,
    limits: LimitsConfig,
    row_budget: int,
) -> LoadedSource:
    """Read one configured local source without mutating it."""

    path = Path(str(source.path).format(date=local_date))
    health: dict[str, Any] = {
        "name": source.name,
        "type": source.kind,
        "path": source.display_path,
        "status": "healthy",
        "items_seen": 0,
        "items_valid": 0,
        "errors": [],
    }
    if not source.enabled:
        health["status"] = "disabled"
        return LoadedSource([], health)
    try:
        stat = path.stat()
    except FileNotFoundError:
        health["status"] = "missing"
        return LoadedSource([], health)
    except OSError as exc:
        health["status"] = "invalid"
        health["errors"] = [_safe_error(exc)]
        return LoadedSource([], health)
    if not path.is_file():
        health["status"] = "invalid"
        health["errors"] = ["source path is not a regular file"]
        return LoadedSource([], health)
    health["size_bytes"] = stat.st_size
    if stat.st_size > limits.max_source_bytes:
        health["status"] = "invalid"
        health["limit_exceeded"] = "max_source_bytes"
        health["errors"] = [
            f"source exceeds max_source_bytes ({limits.max_source_bytes})"
        ]
        return LoadedSource([], health)
    if row_budget <= 0:
        health["status"] = "invalid"
        health["limit_exceeded"] = "max_rows"
        health["errors"] = ["global max_rows budget exhausted"]
        return LoadedSource([], health)

    modified = datetime.fromtimestamp(stat.st_mtime, timezone.utc)
    source_age = _age_hours(modified, now)
    health["modified_at"] = iso_utc(modified)
    health["age_hours"] = round(source_age, 3)
    try:
        rows, parse_errors, rows_examined = _read_rows(source, path, limits, row_budget)
    except SourceLimitError as exc:
        health["status"] = "invalid"
        health["limit_exceeded"] = exc.limit
        health["rows_examined"] = exc.rows_examined
        health["errors"] = [str(exc)]
        return LoadedSource([], health)
    except (OSError, UnicodeError, json.JSONDecodeError, RecursionError, ValueError) as exc:
        health["status"] = "invalid"
        health["errors"] = [_safe_error(exc)]
        return LoadedSource([], health)

    health["items_seen"] = rows_examined
    health["rows_examined"] = rows_examined
    health["errors"] = parse_errors[: limits.max_errors]
    if parse_errors:
        health["status"] = "partial"
    candidates: list[dict[str, Any]] = []
    invalid_rows = 0
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            invalid_rows += 1
            continue
        try:
            candidate = _normalize(
                row, source, index, now, limits.max_engagement_depth
            )
        except (RecursionError, TypeError, ValueError, OverflowError):
            candidate = None
        if candidate is None:
            invalid_rows += 1
        else:
            candidates.append(candidate)
    if invalid_rows > limits.max_errors:
        health["status"] = "invalid"
        health["limit_exceeded"] = "max_errors"
        health["errors"] = [f"max_errors exceeded ({limits.max_errors})"]
        health["items_valid"] = 0
        return LoadedSource([], health)
    if invalid_rows:
        health["errors"].append(f"ignored {invalid_rows} non-object or empty item(s)")
        if health["status"] == "healthy":
            health["status"] = "partial"
    if source_age > source.freshness_hours and health["status"] in {"healthy", "partial"}:
        health["status"] = "stale"
    health["items_valid"] = len(candidates)
    return LoadedSource(candidates, health)


def score_candidate(
    candidate: dict[str, Any],
    source: SourceConfig,
    now: datetime,
    multiplier: float,
) -> dict[str, Any]:
    """Attach a transparent, bounded score to a normalized candidate."""

    published = parse_datetime(candidate.get("published_at"))
    reference_time = published or parse_datetime(candidate.get("observed_at")) or now
    age = _age_hours(reference_time, now)
    freshness = max(0.0, 1.0 - age / source.freshness_hours)
    engagement = min(1.0, math.log10(1.0 + float(candidate.get("engagement", 0))) / 6.0)
    completeness = sum(
        1 for field_name in ("title", "url", "text") if candidate.get(field_name)
    ) / 3.0
    raw_score = 0.15 + 0.5 * freshness + 0.2 * engagement + 0.15 * completeness
    effective_weight = min(4.0, max(0.05, source.weight * multiplier))
    score = min(1.0, raw_score * effective_weight)
    result = dict(candidate)
    result["score"] = round(score, 6)
    result["score_components"] = {
        "freshness": round(freshness, 6),
        "engagement": round(engagement, 6),
        "completeness": round(completeness, 6),
        "source_weight": round(source.weight, 6),
        "feedback_multiplier": round(multiplier, 6),
    }
    return result
