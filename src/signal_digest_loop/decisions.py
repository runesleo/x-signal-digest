"""Decision contract used by humans and external analyzers."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from .errors import ContractError


MEMORY_STATUSES = frozenset({"new", "known", "conflict", "not_checked"})
NOVELTY_LEVELS = frozenset({"none", "low", "medium", "high"})
DISPOSITIONS = frozenset({"discard", "observe", "learn", "act", "content"})
TIMELINESS = frozenset({"now", "soon", "evergreen", "expired"})
EFFORT_LEVELS = frozenset({"none", "low", "medium", "high"})
GATE_STATUSES = frozenset({"not_applicable", "open", "approved", "blocked"})
EVIDENCE_STATUSES = frozenset(
    {"verified", "attributed_unverified", "mixed", "insufficient"}
)
UTILIZATION_ANGLES = frozenset(
    {"business", "product", "strategy", "research", "content", "workflow", "learning"}
)
UTILIZATION_FITS = frozenset({"now", "later", "not_suitable"})


def _source_ref(candidate: dict[str, Any]) -> str:
    """Return the packet field used as the exact review provenance reference."""

    url = candidate.get("url")
    return url if isinstance(url, str) and url else str(candidate.get("source", ""))


def no_signal_decision(
    packet: dict[str, Any] | str,
    reason: str,
    *,
    worth_knowing: list[dict[str, Any]] | None = None,
    discard_reasons: list[str] | None = None,
) -> dict[str, Any]:
    """Create a fully valid zero-promotion decision."""

    packet_id = packet.get("packet_id") if isinstance(packet, dict) else packet
    shortlist = packet.get("shortlist", []) if isinstance(packet, dict) else []
    awareness = list(worth_knowing or [])
    discard_count = len(shortlist) - len(awareness)
    reasons = list(discard_reasons or ([] if discard_count == 0 else [reason]))

    return {
        "schema_version": "1.0",
        "packet_id": packet_id,
        "selection": None,
        "no_signal_reason": reason,
        "claims": [],
        "relation": {"summary": "", "targets": []},
        "memory_check": {"status": "not_checked", "notes": ""},
        "knowledge_delta": {"summary": "", "novelty": "none"},
        "dispositions": [],
        "timeliness": {"status": "expired", "expires_at": None},
        "effort": {"level": "none", "estimate": ""},
        "gates": [],
        "round_review": {
            "schema_version": "1.0",
            "worth_knowing": awareness,
            "formal_selection": {"count": 0, "selected_id": None, "summary": reason},
            "discard_summary": {"count": discard_count, "reasons": reasons},
        },
    }


def _mapping(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ContractError(f"{path} must be an object")
    return value


def _list(value: Any, path: str) -> list[Any]:
    if not isinstance(value, list):
        raise ContractError(f"{path} must be an array")
    return value


def _string(value: Any, path: str, *, allow_empty: bool = True) -> str:
    if not isinstance(value, str) or (not allow_empty and not value.strip()):
        qualifier = "a string" if allow_empty else "a non-empty string"
        raise ContractError(f"{path} must be {qualifier}")
    return value


def _choice(value: Any, choices: frozenset[str], path: str) -> str:
    parsed = _string(value, path, allow_empty=False)
    if parsed not in choices:
        raise ContractError(f"{path} must be one of: {', '.join(sorted(choices))}")
    return parsed


def _exact_fields(value: dict[str, Any], expected: set[str], path: str) -> None:
    actual = set(value)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        details = []
        if missing:
            details.append(f"missing {', '.join(missing)}")
        if extra:
            details.append(f"unknown {', '.join(extra)}")
        raise ContractError(f"{path} must contain exact fields ({'; '.join(details)})")


def _count(value: Any, choices: set[int], path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value not in choices:
        raise ContractError(f"{path} must be one of: {', '.join(str(item) for item in sorted(choices))}")
    return value


def _validate_round_review(
    raw_review: Any,
    packet: dict[str, Any],
    selection: str | None,
    no_signal_reason: str | None,
) -> dict[str, Any]:
    review = _mapping(raw_review, "round_review")
    _exact_fields(
        review,
        {"schema_version", "worth_knowing", "formal_selection", "discard_summary"},
        "round_review",
    )
    if _string(review.get("schema_version"), "round_review.schema_version", allow_empty=False) != "1.0":
        raise ContractError("round_review.schema_version must be exactly 1.0")

    candidates: dict[str, dict[str, Any]] = {}
    for candidate in packet.get("shortlist", []):
        if isinstance(candidate, dict) and isinstance(candidate.get("id"), str):
            candidates[candidate["id"]] = candidate

    worth_knowing = _list(review.get("worth_knowing"), "round_review.worth_knowing")
    if len(worth_knowing) > 3:
        raise ContractError("round_review.worth_knowing must contain at most 3 entries")
    reviewed_ids: list[str] = []
    for index, raw_entry in enumerate(worth_knowing):
        path = f"round_review.worth_knowing[{index}]"
        entry = _mapping(raw_entry, path)
        _exact_fields(
            entry,
            {
                "candidate_id",
                "title",
                "source_ref",
                "why_it_matters",
                "evidence_status",
                "evidence_boundary",
                "utilization_angles",
            },
            path,
        )
        candidate_id = _string(entry.get("candidate_id"), f"{path}.candidate_id", allow_empty=False)
        if candidate_id not in candidates:
            raise ContractError(f"{path}.candidate_id is not present in packet.shortlist")
        if candidate_id in reviewed_ids:
            raise ContractError("round_review.worth_knowing candidate_ids must be unique")
        reviewed_ids.append(candidate_id)
        candidate = candidates[candidate_id]
        title = _string(entry.get("title"), f"{path}.title", allow_empty=False)
        if title != candidate.get("title"):
            raise ContractError(f"{path}.title must exactly match the packet candidate")
        source_ref = _string(
            entry.get("source_ref"), f"{path}.source_ref", allow_empty=False
        )
        if source_ref != _source_ref(candidate):
            raise ContractError(f"{path}.source_ref must exactly match the packet candidate")
        _string(entry.get("why_it_matters"), f"{path}.why_it_matters", allow_empty=False)
        _choice(entry.get("evidence_status"), EVIDENCE_STATUSES, f"{path}.evidence_status")
        _string(entry.get("evidence_boundary"), f"{path}.evidence_boundary", allow_empty=False)
        angles = _list(entry.get("utilization_angles"), f"{path}.utilization_angles")
        if not angles:
            raise ContractError(f"{path}.utilization_angles must contain at least one entry")
        seen_angles: set[str] = set()
        for angle_index, raw_angle in enumerate(angles):
            angle_path = f"{path}.utilization_angles[{angle_index}]"
            angle = _mapping(raw_angle, angle_path)
            _exact_fields(angle, {"angle", "fit", "suggestion"}, angle_path)
            angle_name = _choice(angle.get("angle"), UTILIZATION_ANGLES, f"{angle_path}.angle")
            if angle_name in seen_angles:
                raise ContractError(f"{path}.utilization_angles angles must be unique")
            seen_angles.add(angle_name)
            _choice(angle.get("fit"), UTILIZATION_FITS, f"{angle_path}.fit")
            _string(angle.get("suggestion"), f"{angle_path}.suggestion", allow_empty=False)

    formal = _mapping(review.get("formal_selection"), "round_review.formal_selection")
    _exact_fields(formal, {"count", "selected_id", "summary"}, "round_review.formal_selection")
    expected_count = 0 if selection is None else 1
    if _count(formal.get("count"), {0, 1}, "round_review.formal_selection.count") != expected_count:
        raise ContractError("round_review.formal_selection.count must match top-level selection")
    if formal.get("selected_id") != selection:
        raise ContractError("round_review.formal_selection.selected_id must match top-level selection")
    summary = _string(
        formal.get("summary"), "round_review.formal_selection.summary", allow_empty=False
    )
    if selection is None and summary != no_signal_reason:
        raise ContractError(
            "round_review.formal_selection.summary must match top-level no_signal_reason"
        )
    if selection is not None and selection not in reviewed_ids:
        raise ContractError("top-level selection must be present in round_review.worth_knowing")

    discarded = _mapping(review.get("discard_summary"), "round_review.discard_summary")
    _exact_fields(discarded, {"count", "reasons"}, "round_review.discard_summary")
    expected_discard_count = len(packet.get("shortlist", [])) - len(reviewed_ids)
    discard_count = discarded.get("count")
    if isinstance(discard_count, bool) or not isinstance(discard_count, int) or discard_count < 0:
        raise ContractError("round_review.discard_summary.count must be a non-negative integer")
    if discard_count != expected_discard_count:
        raise ContractError(
            "round_review must reconcile packet.shortlist as worth_knowing plus discarded"
        )
    reasons = _list(discarded.get("reasons"), "round_review.discard_summary.reasons")
    for index, reason in enumerate(reasons):
        _string(reason, f"round_review.discard_summary.reasons[{index}]", allow_empty=False)
    if (discard_count == 0 and reasons) or (discard_count > 0 and not reasons):
        raise ContractError(
            "round_review.discard_summary.reasons must be empty only when discard count is zero"
        )
    return review


def validate_decision(decision: Any, packet: dict[str, Any]) -> dict[str, Any]:
    """Validate and return a shallow copy of a packet-bound decision.

    The schema deliberately carries both epistemic fields (claims, memory
    check, and knowledge delta) and operational fields (disposition,
    timeliness, effort, and gates). This prevents a ranking score from being
    mistaken for a decision.
    """

    value = dict(_mapping(decision, "decision"))
    schema_version = _string(value.get("schema_version"), "schema_version", allow_empty=False)
    if schema_version != "1.0":
        raise ContractError("schema_version must be exactly 1.0")
    packet_id = _string(value.get("packet_id"), "packet_id", allow_empty=False)
    if packet_id != packet.get("packet_id"):
        raise ContractError("decision.packet_id does not match the packet")

    candidate_ids = {
        candidate.get("id")
        for candidate in packet.get("shortlist", [])
        if isinstance(candidate, dict) and isinstance(candidate.get("id"), str)
    }
    selection = value.get("selection")
    no_signal_reason: str | None = None
    if selection is not None:
        selection = _string(selection, "selection", allow_empty=False)
        if selection not in candidate_ids:
            raise ContractError("selection is not present in packet.shortlist")
        try:
            threshold = float(packet.get("policy", {}).get("promotion_threshold", 1.0))
        except (TypeError, ValueError) as exc:
            raise ContractError("packet promotion_threshold must be numeric") from exc
        selected = next(item for item in packet["shortlist"] if item.get("id") == selection)
        try:
            score = float(selected.get("score"))
        except (TypeError, ValueError) as exc:
            raise ContractError("selected candidate has no valid score") from exc
        if score < threshold:
            raise ContractError(
                f"selected candidate score {score:g} is below promotion threshold {threshold:g}"
            )
    else:
        no_signal_reason = _string(
            value.get("no_signal_reason"), "no_signal_reason", allow_empty=False
        )

    claims = _list(value.get("claims"), "claims")
    for index, raw_claim in enumerate(claims):
        claim = _mapping(raw_claim, f"claims[{index}]")
        _string(claim.get("statement"), f"claims[{index}].statement", allow_empty=False)
        evidence = _list(claim.get("evidence"), f"claims[{index}].evidence")
        for evidence_index, item in enumerate(evidence):
            _string(item, f"claims[{index}].evidence[{evidence_index}]", allow_empty=False)
    if selection is not None and not claims:
        raise ContractError("a promoted selection requires at least one claim")

    relation = _mapping(value.get("relation"), "relation")
    _string(relation.get("summary"), "relation.summary", allow_empty=selection is None)
    targets = _list(relation.get("targets"), "relation.targets")
    for index, target in enumerate(targets):
        _string(target, f"relation.targets[{index}]", allow_empty=False)

    memory = _mapping(value.get("memory_check"), "memory_check")
    _choice(memory.get("status"), MEMORY_STATUSES, "memory_check.status")
    _string(memory.get("notes"), "memory_check.notes")

    delta = _mapping(value.get("knowledge_delta"), "knowledge_delta")
    _string(delta.get("summary"), "knowledge_delta.summary", allow_empty=selection is None)
    _choice(delta.get("novelty"), NOVELTY_LEVELS, "knowledge_delta.novelty")

    dispositions = _list(value.get("dispositions"), "dispositions")
    for index, raw_disposition in enumerate(dispositions):
        disposition = _mapping(raw_disposition, f"dispositions[{index}]")
        _choice(disposition.get("type"), DISPOSITIONS, f"dispositions[{index}].type")
        _string(
            disposition.get("rationale"),
            f"dispositions[{index}].rationale",
            allow_empty=False,
        )
        _string(disposition.get("route"), f"dispositions[{index}].route", allow_empty=False)
        if "next_action" in disposition:
            _string(disposition["next_action"], f"dispositions[{index}].next_action")
    if selection is not None and not dispositions:
        raise ContractError("a promoted selection requires at least one disposition")
    disposition_types = [item.get("type") for item in dispositions if isinstance(item, dict)]
    if "discard" in disposition_types and len(disposition_types) != 1:
        raise ContractError("discard is exclusive and cannot be combined with another disposition")

    timeliness = _mapping(value.get("timeliness"), "timeliness")
    _choice(timeliness.get("status"), TIMELINESS, "timeliness.status")
    expires_at = timeliness.get("expires_at")
    if expires_at is not None:
        raw_expiry = _string(expires_at, "timeliness.expires_at", allow_empty=False)
        try:
            parsed_expiry = datetime.fromisoformat(raw_expiry.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ContractError("timeliness.expires_at must be an ISO-8601 timestamp") from exc
        if parsed_expiry.tzinfo is None:
            raise ContractError("timeliness.expires_at must include a timezone")

    effort = _mapping(value.get("effort"), "effort")
    _choice(effort.get("level"), EFFORT_LEVELS, "effort.level")
    _string(effort.get("estimate"), "effort.estimate")

    gates = _list(value.get("gates"), "gates")
    for index, raw_gate in enumerate(gates):
        gate = _mapping(raw_gate, f"gates[{index}]")
        _string(gate.get("name"), f"gates[{index}].name", allow_empty=False)
        _choice(gate.get("status"), GATE_STATUSES, f"gates[{index}].status")
        if "notes" in gate:
            _string(gate["notes"], f"gates[{index}].notes")

    _validate_round_review(value.get("round_review"), packet, selection, no_signal_reason)

    if selection is None:
        # A null selection is a strict abstention, not a side channel for
        # unbound claims or actions. Keep every operational field inert.
        if claims:
            raise ContractError("selection=null requires claims to be empty")
        if dispositions:
            raise ContractError("selection=null requires dispositions to be empty")
        if targets:
            raise ContractError("selection=null requires relation.targets to be empty")
        if delta.get("novelty") != "none":
            raise ContractError("selection=null requires knowledge_delta.novelty=none")
        if timeliness.get("status") != "expired" or expires_at is not None:
            raise ContractError(
                "selection=null requires timeliness.status=expired and expires_at=null"
            )
        if effort.get("level") != "none":
            raise ContractError("selection=null requires effort.level=none")

    return value
