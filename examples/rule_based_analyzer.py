#!/usr/bin/env python3
"""A deterministic, standard-library analyzer for the fictional example."""

from __future__ import annotations

import json
import sys
from typing import Any


ACTION_WORDS = {"actionable", "change", "deadline", "maintenance", "migration"}


def _source_ref(candidate: dict[str, Any]) -> str:
    return str(candidate.get("url") or candidate.get("source") or "")


def _review_entry(candidate: dict[str, Any], index: int) -> dict[str, Any]:
    statuses = ("attributed_unverified", "insufficient", "mixed")
    angles = ("workflow", "research", "learning")
    return {
        "candidate_id": candidate["id"],
        "title": candidate.get("title"),
        "source_ref": _source_ref(candidate),
        "why_it_matters": (
            "It may change a reversible maintenance decision."
            if index == 0
            else "It provides context that may be useful in a later review."
        ),
        "evidence_status": statuses[min(index, len(statuses) - 1)],
        "evidence_boundary": "Fictional source artifact only; no external verification was performed.",
        "utilization_angles": [
            {
                "angle": angles[min(index, len(angles) - 1)],
                "fit": "now" if index == 0 else "later",
                "suggestion": (
                    "Review the reversible readiness check."
                    if index == 0
                    else "Retain as fictional context for a future review."
                ),
            }
        ],
    }


def _words(candidate: dict[str, Any]) -> set[str]:
    parts = [
        str(candidate.get("title", "")),
        str(candidate.get("text", "")),
    ]
    return {
        word.strip(".,:;!?()[]{}\"'").lower()
        for word in " ".join(parts).split()
        if word.strip()
    }


def analyze(packet: dict[str, Any]) -> dict[str, Any]:
    packet_id = packet.get("packet_id")
    if not isinstance(packet_id, str) or not packet_id:
        raise ValueError("packet_id is required")

    shortlist = packet.get("shortlist", [])
    if not isinstance(shortlist, list):
        raise ValueError("shortlist must be a list")
    policy = packet.get("policy", {})
    if not isinstance(policy, dict):
        raise ValueError("policy must be an object")
    threshold = float(policy.get("promotion_threshold", 1.0))

    reviewed_candidates = [item for item in shortlist[:3] if isinstance(item, dict)]
    worth_knowing = [
        _review_entry(candidate, index)
        for index, candidate in enumerate(reviewed_candidates)
    ]
    discard_count = len(shortlist) - len(worth_knowing)
    discard_summary = {
        "count": discard_count,
        "reasons": [] if discard_count == 0 else ["Ranked below the three-item awareness limit."],
    }

    for candidate in shortlist:
        if not isinstance(candidate, dict):
            continue
        if float(candidate.get("score", 0.0)) < threshold:
            continue
        if ACTION_WORDS.intersection(_words(candidate)):
            return {
                "schema_version": "1.0",
                "packet_id": packet_id,
                "selection": candidate["id"],
                "claims": [
                    {
                        "statement": (
                            "The fictional item describes a configuration migration."
                        ),
                        "evidence": [candidate.get("url") or candidate["id"]],
                    }
                ],
                "relation": {
                    "summary": "The item is relevant to maintenance readiness.",
                    "targets": ["maintenance_review"],
                },
                "memory_check": {
                    "status": "not_checked",
                    "notes": "The synthetic demo has no memory adapter.",
                },
                "knowledge_delta": {
                    "summary": "A new fictional readiness check is available.",
                    "novelty": "medium",
                },
                "dispositions": [
                    {
                        "type": "act",
                        "route": "maintenance_review",
                        "rationale": (
                            "The fictional item is time-bounded and the check is "
                            "reversible."
                        ),
                        "next_action": (
                            "Review the example configuration before the fictional date."
                        ),
                    }
                ],
                "timeliness": {"status": "soon", "expires_at": None},
                "effort": {"level": "low", "estimate": "15 minutes"},
                "gates": [
                    {
                        "name": "external_action",
                        "status": "not_applicable",
                        "notes": "Synthetic demo only.",
                    }
                ],
                "round_review": {
                    "schema_version": "1.0",
                    "worth_knowing": worth_knowing,
                    "formal_selection": {
                        "count": 1,
                        "selected_id": candidate["id"],
                        "summary": "One fictional maintenance item cleared the formal decision gate.",
                    },
                    "discard_summary": discard_summary,
                },
            }

    no_signal_reason = "No fictional candidate contains an actionable marker."
    return {
        "schema_version": "1.0",
        "packet_id": packet_id,
        "selection": None,
        "no_signal_reason": no_signal_reason,
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
            "worth_knowing": worth_knowing,
            "formal_selection": {
                "count": 0,
                "selected_id": None,
                "summary": no_signal_reason,
            },
            "discard_summary": discard_summary,
        },
    }


def main() -> int:
    try:
        packet = json.load(sys.stdin)
        decision = analyze(packet)
        json.dump(decision, sys.stdout, ensure_ascii=False, separators=(",", ":"))
        sys.stdout.write("\n")
        return 0
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        print(f"analyzer error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
