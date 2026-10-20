"""Core prepare → analyze → commit → digest → feedback operations."""

from __future__ import annotations

import json
import math
import os
import re
import subprocess
import tempfile
from collections import Counter
from collections.abc import Sequence
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .config import Settings
from .decisions import no_signal_decision, validate_decision
from .errors import ConfigError, ContractError
from .sources import iso_utc, load_source, parse_datetime, score_candidate
from .storage import (
    atomic_write_json,
    canonical_json,
    content_hash,
    exclusive_lock,
    read_json,
    safe_name,
)


PACKET_SCHEMA = "1.0"
RECEIPT_SCHEMA = "1.0"
STATE_SCHEMA = "1.0"
MAX_ANALYZER_STDOUT_BYTES = 1_048_576
MAX_ANALYZER_STDERR_BYTES = 65_536


def utc_now() -> datetime:
    """Return the current aware UTC time; split out for deterministic tests."""

    return datetime.now(timezone.utc)


def _timezone(settings: Settings) -> ZoneInfo:
    try:
        return ZoneInfo(settings.timezone)
    except ZoneInfoNotFoundError as exc:
        raise ConfigError(f"unknown timezone: {settings.timezone}") from exc


def _empty_state() -> dict[str, Any]:
    return {
        "schema_version": STATE_SCHEMA,
        "updated_at": None,
        "processed": {},
        "source_weight_multipliers": {},
        "feedback_reversals": {},
    }


def _state_path(settings: Settings) -> Path:
    return settings.state_dir / "state.json"


def _lock_path(settings: Settings) -> Path:
    return settings.state_dir / ".state.lock"


def _load_state(settings: Settings, now: datetime) -> dict[str, Any]:
    raw = read_json(_state_path(settings), default=None)
    if raw is None:
        return _empty_state()
    if not isinstance(raw, dict):
        raise ContractError("state.json must contain an object")
    state = _empty_state()
    state.update(raw)
    for key in ("processed", "source_weight_multipliers", "feedback_reversals"):
        if not isinstance(state.get(key), dict):
            raise ContractError(f"state.{key} must be an object")
    active: dict[str, Any] = {}
    for candidate_id, entry in state["processed"].items():
        if not isinstance(candidate_id, str) or not isinstance(entry, dict):
            continue
        expires = parse_datetime(entry.get("expires_at"))
        if expires is None or expires > now:
            active[candidate_id] = entry
    state["processed"] = active
    return state


def _effective_multiplier(state: dict[str, Any], source_name: str) -> float:
    value = state["source_weight_multipliers"].get(source_name, 1.0)
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return 1.0
    return parsed if math.isfinite(parsed) and parsed > 0 else 1.0


def _deduplicate(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    winners: dict[str, dict[str, Any]] = {}
    duplicates: dict[str, set[str]] = {}
    for candidate in candidates:
        fingerprint = str(candidate["fingerprint"])
        duplicates.setdefault(fingerprint, set()).add(str(candidate["source"]))
        current = winners.get(fingerprint)
        if current is None or (candidate["score"], candidate["id"]) > (
            current["score"],
            current["id"],
        ):
            winners[fingerprint] = candidate
    result: list[dict[str, Any]] = []
    for fingerprint, winner in winners.items():
        item = dict(winner)
        item["duplicate_sources"] = sorted(duplicates[fingerprint] - {str(item["source"])})
        result.append(item)
    return result


def prepare_packet(settings: Settings, *, now: datetime | None = None) -> dict[str, Any]:
    """Read local sources and produce a deterministic review packet.

    Preparation is deliberately non-promotional. It health-checks adapters,
    rejects stale source output, normalizes and de-duplicates candidates,
    excludes recently processed items, ranks the remainder, and identifies at
    most one *suggested* promotion for a later decision.
    """

    current = (now or utc_now()).astimezone(timezone.utc)
    local_date = current.astimezone(_timezone(settings)).date().isoformat()
    state = _load_state(settings, current)
    health_rows: list[dict[str, Any]] = []
    scored: list[dict[str, Any]] = []
    stale_candidate_count = 0
    remaining_rows = settings.limits.max_rows
    for source in settings.sources:
        loaded = load_source(
            source,
            current,
            local_date,
            settings.limits,
            remaining_rows,
        )
        health_rows.append(loaded.health)
        examined = loaded.health.get("rows_examined", 0)
        if isinstance(examined, int) and examined > 0:
            remaining_rows = max(0, remaining_rows - min(remaining_rows, examined))
        if loaded.health["status"] in {"stale", "missing", "invalid", "disabled"}:
            stale_candidate_count += len(loaded.candidates)
            continue
        multiplier = _effective_multiplier(state, source.name)
        scored.extend(
            score_candidate(candidate, source, current, multiplier)
            for candidate in loaded.candidates
        )

    deduplicated = _deduplicate(scored)
    unprocessed = [candidate for candidate in deduplicated if candidate["id"] not in state["processed"]]
    unprocessed.sort(key=lambda item: (-float(item["score"]), str(item["id"])))
    shortlist = unprocessed[: settings.loop.shortlist_limit]
    suggested = (
        shortlist[0]["id"]
        if shortlist and float(shortlist[0]["score"]) >= settings.loop.promotion_threshold
        else None
    )
    created_at = iso_utc(current)
    identity = {
        "created_at": created_at,
        "health": health_rows,
        "shortlist": [(item["id"], item["score"]) for item in shortlist],
    }
    packet_id = f"pkt_{content_hash(identity, 24)}"
    packet = {
        "schema_version": PACKET_SCHEMA,
        "packet_id": packet_id,
        "created_at": created_at,
        "local_date": local_date,
        "policy": {
            "promotion_limit": 1,
            "promotion_threshold": settings.loop.promotion_threshold,
            "shortlist_limit": settings.loop.shortlist_limit,
            "stale_sources_eligible": False,
            "resource_limits": {
                "max_source_bytes": settings.limits.max_source_bytes,
                "max_rows": settings.limits.max_rows,
                "max_line_bytes": settings.limits.max_line_bytes,
                "max_errors": settings.limits.max_errors,
                "max_engagement_depth": settings.limits.max_engagement_depth,
            },
        },
        "source_health": health_rows,
        "counts": {
            "normalized": len(scored),
            "deduplicated": len(deduplicated),
            "excluded_as_processed": len(deduplicated) - len(unprocessed),
            "excluded_from_stale_sources": stale_candidate_count,
            "shortlisted": len(shortlist),
        },
        "shortlist": shortlist,
        "suggested_promotion": suggested,
    }
    packet_dir = settings.state_dir / "packets"
    atomic_write_json(packet_dir / f"{safe_name(packet_id)}.json", packet)
    atomic_write_json(packet_dir / "latest.json", packet)
    return packet


def _load_packet(value: dict[str, Any] | str | Path, settings: Settings) -> dict[str, Any]:
    if isinstance(value, dict):
        packet = value
    else:
        raw = str(value)
        if raw == "latest":
            path = settings.state_dir / "packets" / "latest.json"
        else:
            candidate_path = Path(raw).expanduser()
            path = (
                candidate_path
                if candidate_path.is_absolute() or candidate_path.exists()
                else settings.state_dir / "packets" / f"{safe_name(raw)}.json"
            )
        packet = read_json(path, default=None)
        if packet is None:
            raise ContractError(f"packet not found: {raw}")
    if not isinstance(packet, dict) or not isinstance(packet.get("packet_id"), str):
        raise ContractError("packet must be an object with packet_id")
    shortlist = packet.get("shortlist")
    if not isinstance(shortlist, list):
        raise ContractError("packet.shortlist must be an array")
    if int(packet.get("policy", {}).get("promotion_limit", 0)) != 1:
        raise ContractError("packet promotion_limit must be exactly 1")
    return packet


def _mark_processed(
    state: dict[str, Any],
    packet: dict[str, Any],
    selection: str | None,
    committed_at: datetime,
    ttl_hours: float,
) -> None:
    expires = iso_utc(committed_at + timedelta(hours=ttl_hours))
    for candidate in packet["shortlist"]:
        if not isinstance(candidate, dict) or not isinstance(candidate.get("id"), str):
            continue
        candidate_id = candidate["id"]
        state["processed"][candidate_id] = {
            "source": candidate.get("source"),
            "fingerprint": candidate.get("fingerprint"),
            "status": "promoted" if candidate_id == selection else "reviewed",
            "processed_at": iso_utc(committed_at),
            "expires_at": expires,
        }


def commit_decision(
    settings: Settings,
    packet: dict[str, Any] | str | Path,
    decision: dict[str, Any],
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Validate and atomically record one zero-or-one promotion decision.

    The operation is idempotent for the same packet and decision. State and
    receipt files are each written via atomic replacement while a single
    workspace lock prevents concurrent commits.
    """

    resolved_packet = _load_packet(packet, settings)
    validated = validate_decision(decision, resolved_packet)
    selection = validated.get("selection")
    if selection is not None and not isinstance(selection, str):
        raise ContractError("selection must be a candidate id or null")
    committed_at = (now or utc_now()).astimezone(timezone.utc)
    receipt_identity = {
        "packet_id": resolved_packet["packet_id"],
        "decision": validated,
    }
    receipt_id = f"rcpt_{content_hash(receipt_identity, 28)}"
    receipt_path = settings.state_dir / "receipts" / "commits" / f"{safe_name(receipt_id)}.json"
    selected_candidate = next(
        (candidate for candidate in resolved_packet["shortlist"] if candidate.get("id") == selection),
        None,
    )
    receipt = {
        "schema_version": RECEIPT_SCHEMA,
        "type": "commit",
        "receipt_id": receipt_id,
        "committed_at": iso_utc(committed_at),
        "packet_id": resolved_packet["packet_id"],
        "packet_digest": content_hash(resolved_packet, 64),
        "selection": selection,
        "selected_candidate": selected_candidate,
        "decision": validated,
        "round_review": validated["round_review"],
        "reviewed_candidate_ids": [
            candidate["id"]
            for candidate in resolved_packet["shortlist"]
            if isinstance(candidate, dict) and isinstance(candidate.get("id"), str)
        ],
        "source_health": resolved_packet.get("source_health", []),
    }
    with exclusive_lock(_lock_path(settings)):
        existing = read_json(receipt_path, default=None)
        if existing is not None:
            if not isinstance(existing, dict) or existing.get("packet_digest") != receipt["packet_digest"]:
                raise ContractError(f"receipt id collision: {receipt_id}")
            return existing
        state = _load_state(settings, committed_at)
        _mark_processed(
            state,
            resolved_packet,
            selection,
            committed_at,
            settings.loop.processed_ttl_hours,
        )
        state["updated_at"] = iso_utc(committed_at)
        # State first makes a retry safe if interruption occurs before receipt
        # creation; the deterministic receipt id completes the transaction.
        atomic_write_json(_state_path(settings), state)
        atomic_write_json(receipt_path, receipt)
    return receipt


def run_command_analyzer(
    packet: dict[str, Any],
    command: Sequence[str],
    *,
    timeout_seconds: float,
    working_directory: Path,
) -> dict[str, Any]:
    """Run an explicitly allowed analyzer with strict JSON stdio.

    The command is always launched with ``shell=False``, a small environment,
    bounded execution time, and a bounded accepted output size. Analyzer logs
    belong on stderr; stdout must contain one JSON decision object.
    """

    if not command or not all(isinstance(part, str) and part for part in command):
        raise ContractError("analyzer command must be a non-empty string array")
    environment = {
        "PATH": os.environ.get("PATH", ""),
        "PYTHONIOENCODING": "utf-8",
        "SIGNAL_DIGEST_PACKET_SCHEMA": PACKET_SCHEMA,
    }
    if os.name == "nt" and "SYSTEMROOT" in os.environ:
        environment["SYSTEMROOT"] = os.environ["SYSTEMROOT"]
    with tempfile.TemporaryFile() as stdout_file, tempfile.TemporaryFile() as stderr_file:
        try:
            process = subprocess.Popen(
                list(command),
                stdin=subprocess.PIPE,
                stdout=stdout_file,
                stderr=stderr_file,
                cwd=working_directory,
                env=environment,
                shell=False,
            )
            process.communicate(input=canonical_json(packet), timeout=timeout_seconds)
        except subprocess.TimeoutExpired as exc:
            process.kill()
            process.communicate()
            raise ContractError(f"analyzer timed out after {timeout_seconds:g}s") from exc
        except OSError as exc:
            raise ContractError(f"cannot start analyzer: {exc}") from exc
        stdout_file.seek(0)
        stdout = stdout_file.read(MAX_ANALYZER_STDOUT_BYTES + 1)
        stderr_file.seek(0)
        stderr = stderr_file.read(MAX_ANALYZER_STDERR_BYTES + 1)
    if len(stdout) > MAX_ANALYZER_STDOUT_BYTES:
        raise ContractError("analyzer stdout exceeds 1 MiB")
    if process.returncode != 0:
        detail = stderr[:MAX_ANALYZER_STDERR_BYTES].decode("utf-8", errors="replace").strip()
        raise ContractError(f"analyzer exited with {process.returncode}: {detail}")
    try:
        decision = json.loads(stdout.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ContractError(f"analyzer stdout is not one JSON decision object: {exc}") from exc
    return validate_decision(decision, packet)


def run_cycle(
    settings: Settings,
    *,
    analyzer_command: Sequence[str] | None = None,
    allow_command_analyzer: bool = False,
    apply: bool = False,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Prepare, optionally analyze, and optionally commit one automatic cycle.

    This method is dry-safe by default: without ``apply=True`` it never writes
    processed state or receipts. A configured or supplied executable is not run
    unless ``allow_command_analyzer=True`` is also explicit.
    """

    packet = prepare_packet(settings, now=now)
    command = tuple(analyzer_command) if analyzer_command is not None else settings.analyzer.command
    if command:
        if not allow_command_analyzer:
            raise ContractError(
                "command analyzer is configured but disabled; explicitly allow it for this cycle"
            )
        decision = run_command_analyzer(
            packet,
            command,
            timeout_seconds=settings.analyzer.timeout_seconds,
            working_directory=settings.config_path.parent,
        )
    else:
        decision = no_signal_decision(packet, "no analyzer configured; nothing promoted")
    result: dict[str, Any] = {
        "status": "committed" if apply else "dry_run",
        "packet": packet,
        "decision": decision,
        "receipt": None,
    }
    if apply:
        result["receipt"] = commit_decision(settings, packet, decision, now=now)
    return result


def _commit_receipts(settings: Settings) -> list[dict[str, Any]]:
    directory = settings.state_dir / "receipts" / "commits"
    receipts: list[dict[str, Any]] = []
    if not directory.is_dir():
        return receipts
    for path in sorted(directory.glob("*.json")):
        try:
            payload = read_json(path)
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(payload, dict) and payload.get("type") == "commit":
            receipts.append(payload)
    return receipts


def create_digest(settings: Settings, *, date: str | None = None) -> dict[str, Any]:
    """Create a summary using commit receipts as its only input data."""

    receipts = _commit_receipts(settings)
    if date is not None:
        receipts = [
            receipt
            for receipt in receipts
            if str(receipt.get("committed_at", ""))[:10] == date
        ]
    promoted = [receipt for receipt in receipts if receipt.get("selection") is not None]
    source_counts = Counter(
        str(receipt.get("selected_candidate", {}).get("source"))
        for receipt in promoted
        if isinstance(receipt.get("selected_candidate"), dict)
        and receipt["selected_candidate"].get("source")
    )
    disposition_counts: Counter[str] = Counter()
    entries: list[dict[str, Any]] = []
    round_review_count = 0
    worth_knowing_entries: list[dict[str, Any]] = []
    for receipt in receipts:
        review = receipt.get("round_review")
        decision = receipt.get("decision")
        if (
            not isinstance(review, dict)
            or not isinstance(decision, dict)
            or decision.get("round_review") != review
            or review.get("schema_version") != "1.0"
        ):
            continue
        awareness = review.get("worth_knowing")
        reviewed_ids = receipt.get("reviewed_candidate_ids")
        if not isinstance(awareness, list) or not isinstance(reviewed_ids, list):
            continue
        round_review_count += 1
        for item in awareness:
            if not isinstance(item, dict) or item.get("candidate_id") not in reviewed_ids:
                continue
            candidate_id = item.get("candidate_id")
            worth_knowing_entries.append(
                {
                    "receipt_id": receipt.get("receipt_id"),
                    "packet_id": receipt.get("packet_id"),
                    "committed_at": receipt.get("committed_at"),
                    "candidate_id": candidate_id,
                    "title": item.get("title"),
                    "source_ref": item.get("source_ref"),
                    "evidence_status": item.get("evidence_status"),
                    "why_it_matters": item.get("why_it_matters"),
                    "evidence_boundary": item.get("evidence_boundary"),
                    "utilization_angles": item.get("utilization_angles", []),
                    "formal_selected": candidate_id == receipt.get("selection"),
                }
            )
    for receipt in promoted:
        decision = receipt.get("decision", {})
        dispositions = decision.get("dispositions", []) if isinstance(decision, dict) else []
        types = [
            str(item["type"])
            for item in dispositions
            if isinstance(item, dict) and isinstance(item.get("type"), str)
        ]
        disposition_counts.update(types)
        candidate = receipt.get("selected_candidate", {})
        entries.append(
            {
                "receipt_id": receipt.get("receipt_id"),
                "committed_at": receipt.get("committed_at"),
                "candidate_id": receipt.get("selection"),
                "source": candidate.get("source") if isinstance(candidate, dict) else None,
                "title": candidate.get("title") if isinstance(candidate, dict) else None,
                "url": candidate.get("url") if isinstance(candidate, dict) else None,
                "dispositions": types,
                "claims": decision.get("claims", []) if isinstance(decision, dict) else [],
                "knowledge_delta": decision.get("knowledge_delta") if isinstance(decision, dict) else None,
            }
        )
    return {
        "schema_version": "1.0",
        "date": date,
        "receipt_count": len(receipts),
        "promotion_count": len(promoted),
        "no_signal_count": len(receipts) - len(promoted),
        "round_review_count": round_review_count,
        "worth_knowing_count": len(worth_knowing_entries),
        "worth_knowing_entries": worth_knowing_entries,
        "sources": dict(sorted(source_counts.items())),
        "dispositions": dict(sorted(disposition_counts.items())),
        "entries": entries,
    }


def digest_markdown(digest: dict[str, Any]) -> str:
    """Render a receipt-derived digest as compact Markdown."""

    title_date = digest.get("date") or "all time"
    lines = [
        f"# Signal digest — {title_date}",
        "",
        f"- Cycles committed: {digest['receipt_count']}",
        f"- Worth knowing: {digest.get('worth_knowing_count', 0)}",
        f"- Signals promoted: {digest['promotion_count']}",
        f"- No-signal cycles: {digest['no_signal_count']}",
    ]
    awareness_entries = digest.get("worth_knowing_entries", [])
    if awareness_entries:
        lines.extend(["", "## Worth knowing", ""])
        for entry in awareness_entries:
            title = _markdown_text(entry.get("title") or entry.get("candidate_id") or "Untitled signal")
            source_ref = entry.get("source_ref")
            safe_ref = (
                str(source_ref).replace(" ", "%20").replace(")", "%29")
                if str(source_ref).startswith(("http://", "https://"))
                else ""
            )
            label = f"[{title}]({safe_ref})" if safe_ref else title
            evidence_status = _markdown_text(entry.get("evidence_status") or "unspecified")
            selected_marker = " — formally selected" if entry.get("formal_selected") else ""
            lines.append(f"### {label}")
            lines.append(f"- Evidence status: {evidence_status}{selected_marker}")
            lines.append(f"- Why it matters: {_markdown_text(entry.get('why_it_matters') or '')}")
            lines.append(
                f"- Evidence boundary: {_markdown_text(entry.get('evidence_boundary') or '')}"
            )
            angles = entry.get("utilization_angles", [])
            for angle in angles if isinstance(angles, list) else []:
                if not isinstance(angle, dict):
                    continue
                name = _markdown_text(angle.get("angle") or "unspecified")
                fit = _markdown_text(angle.get("fit") or "unspecified")
                suggestion = _markdown_text(angle.get("suggestion") or "")
                lines.append(f"- Utilization ({name}, {fit}): {suggestion}")
            lines.append("")
    entries = digest.get("entries", [])
    if entries:
        lines.extend(["", "## Formal selections", ""])
        for entry in entries:
            title = _markdown_text(entry.get("title") or entry.get("candidate_id") or "Untitled signal")
            url = entry.get("url")
            safe_url = str(url).replace(" ", "%20").replace(")", "%29") if str(url).startswith(("http://", "https://")) else ""
            label = f"[{title}]({safe_url})" if safe_url else title
            dispositions = ", ".join(_markdown_text(item) for item in entry.get("dispositions", [])) or "unspecified"
            source = _markdown_text(entry.get("source", "unknown"))
            lines.append(f"- {label} — {source} — {dispositions}")
    return "\n".join(lines) + "\n"


def _markdown_text(value: Any) -> str:
    """Escape receipt-controlled text before embedding it in Markdown."""

    text = re.sub(r"[\x00-\x1f\x7f]", " ", str(value))
    text = " ".join(text.split())
    for token in ("\\", "`", "*", "_", "[", "]", "<", ">"):
        text = text.replace(token, f"\\{token}")
    return text


def submit_feedback(
    settings: Settings,
    *,
    source: str | None = None,
    outcome: str | None = None,
    amount: float | None = None,
    undo_receipt_id: str | None = None,
    apply: bool = False,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Preview or apply a bounded source-weight adjustment, with exact undo.

    Positive and negative outcomes move a source multiplier by at most the
    configured maximum step. Undo is fail-closed and only succeeds while the
    source is still at the value produced by the target feedback receipt.
    """

    current_time = (now or utc_now()).astimezone(timezone.utc)
    if undo_receipt_id:
        return _undo_feedback(settings, undo_receipt_id, apply=apply, now=current_time)
    source_names = {item.name for item in settings.sources}
    if source not in source_names:
        raise ContractError(f"unknown feedback source: {source!r}")
    if outcome not in {"positive", "negative", "neutral"}:
        raise ContractError("outcome must be positive, negative, or neutral")
    step = settings.loop.feedback_step if amount is None else float(amount)
    if not math.isfinite(step) or step < 0:
        raise ContractError("feedback amount must be a finite non-negative number")
    if step > settings.loop.feedback_max_step:
        raise ContractError(
            f"feedback amount exceeds configured maximum {settings.loop.feedback_max_step:g}"
        )
    direction = 1 if outcome == "positive" else -1 if outcome == "negative" else 0
    with exclusive_lock(_lock_path(settings)) if apply else _null_lock():
        state = _load_state(settings, current_time)
        before = _effective_multiplier(state, source)
        after = min(
            settings.loop.feedback_max_multiplier,
            max(settings.loop.feedback_min_multiplier, before + direction * step),
        )
        event = {
            "schema_version": RECEIPT_SCHEMA,
            "type": "feedback",
            "action": "adjust",
            "created_at": iso_utc(current_time),
            "source": source,
            "outcome": outcome,
            "requested_step": step,
            "previous_multiplier": round(before, 6),
            "new_multiplier": round(after, 6),
        }
        receipt_id = f"fb_{content_hash(event, 28)}"
        event["receipt_id"] = receipt_id
        event["status"] = "applied" if apply else "preview"
        if apply:
            state["source_weight_multipliers"][source] = round(after, 6)
            state["updated_at"] = iso_utc(current_time)
            atomic_write_json(_state_path(settings), state)
            atomic_write_json(
                settings.state_dir / "receipts" / "feedback" / f"{safe_name(receipt_id)}.json",
                event,
            )
        return event


class _null_lock:
    """Tiny context manager used to share preview and apply code paths."""

    def __enter__(self) -> None:
        return None

    def __exit__(self, *_: object) -> None:
        return None


def _undo_feedback(
    settings: Settings,
    receipt_id: str,
    *,
    apply: bool,
    now: datetime,
) -> dict[str, Any]:
    target_path = settings.state_dir / "receipts" / "feedback" / f"{safe_name(receipt_id)}.json"
    target = read_json(target_path, default=None)
    if not isinstance(target, dict) or target.get("type") != "feedback" or target.get("action") != "adjust":
        raise ContractError(f"feedback receipt not found or not reversible: {receipt_id}")
    source = target.get("source")
    if not isinstance(source, str):
        raise ContractError("feedback receipt has no source")
    with exclusive_lock(_lock_path(settings)) if apply else _null_lock():
        state = _load_state(settings, now)
        if receipt_id in state["feedback_reversals"]:
            raise ContractError(f"feedback receipt is already reversed: {receipt_id}")
        current = _effective_multiplier(state, source)
        expected = float(target["new_multiplier"])
        before = float(target["previous_multiplier"])
        if not math.isclose(current, expected, abs_tol=1e-9):
            raise ContractError(
                "feedback cannot be undone after a later adjustment; undo newer receipts first"
            )
        event = {
            "schema_version": RECEIPT_SCHEMA,
            "type": "feedback",
            "action": "undo",
            "created_at": iso_utc(now),
            "source": source,
            "target_receipt_id": receipt_id,
            "previous_multiplier": round(current, 6),
            "new_multiplier": round(before, 6),
        }
        undo_id = f"fb_{content_hash(event, 28)}"
        event["receipt_id"] = undo_id
        event["status"] = "applied" if apply else "preview"
        if apply:
            state["source_weight_multipliers"][source] = round(before, 6)
            state["feedback_reversals"][receipt_id] = undo_id
            state["updated_at"] = iso_utc(now)
            atomic_write_json(_state_path(settings), state)
            atomic_write_json(
                settings.state_dir / "receipts" / "feedback" / f"{safe_name(undo_id)}.json",
                event,
            )
        return event
