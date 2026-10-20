#!/usr/bin/env python3
"""Run a privacy-safe fictional digest demo from a standalone Skill."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


PRODUCT_ROOT = Path(__file__).resolve().parents[3]


def _adjacent_demo() -> Path | None:
    demo = PRODUCT_ROOT / "demo.py"
    package = PRODUCT_ROOT / "src" / "signal_digest_loop" / "__init__.py"
    return demo if demo.is_file() and package.is_file() else None


def _kernel_payload(demo: Path) -> dict[str, Any]:
    completed = subprocess.run(
        [sys.executable, str(demo), "--json"],
        cwd=PRODUCT_ROOT,
        check=False,
        shell=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or f"exit {completed.returncode}"
        raise RuntimeError(f"companion kernel demo failed: {detail}")
    payload = json.loads(completed.stdout)
    payload.update(
        {
            "demo_only": True,
            "kernel_exercised": True,
            "action_executed": False,
            "receipt_persisted": False,
        }
    )
    selected = payload.get("selected")
    if isinstance(selected, dict):
        selected["proposed_dispositions"] = selected.pop("dispositions", [])
    return payload


def _portable_payload() -> dict[str, Any]:
    worth_knowing = [
        {
            "candidate_id": "demo_cache_change",
            "title": "Fictional cache policy changes next week",
            "source_ref": "https://example.invalid/notes/cache-change",
            "why_it_matters": "It may change a reversible maintenance decision.",
            "evidence_status": "attributed_unverified",
            "evidence_boundary": "Fictional source row only; no external verification was performed.",
            "utilization_angles": [
                {
                    "angle": "workflow",
                    "fit": "now",
                    "suggestion": "Review the fictional readiness check.",
                }
            ],
        },
        {
            "candidate_id": "demo_cache_research",
            "title": "Imaginary research team publishes a cache visualization method",
            "source_ref": "https://example.invalid/research/palette",
            "why_it_matters": "It provides context for a later research review.",
            "evidence_status": "insufficient",
            "evidence_boundary": "Fictional source row only; no external verification was performed.",
            "utilization_angles": [
                {
                    "angle": "research",
                    "fit": "later",
                    "suggestion": "Retain as fictional context for a future review.",
                }
            ],
        },
        {
            "candidate_id": "demo_learning_checklist",
            "title": "Example community shares a lightweight learning checklist",
            "source_ref": "https://example.invalid/community/hello",
            "why_it_matters": "It demonstrates awareness without formal promotion.",
            "evidence_status": "mixed",
            "evidence_boundary": "Fictional source row only; no external verification was performed.",
            "utilization_angles": [
                {
                    "angle": "learning",
                    "fit": "later",
                    "suggestion": "Retain as fictional context for a future review.",
                }
            ],
        },
    ]
    receipt_material = json.dumps(worth_knowing, sort_keys=True, separators=(",", ":"))
    receipt_id = "demo_rcpt_" + hashlib.sha256(receipt_material.encode()).hexdigest()[:24]
    round_review = {
        "schema_version": "1.0",
        "worth_knowing": worth_knowing,
        "formal_selection": {
            "count": 1,
            "selected_id": "demo_cache_change",
            "summary": "One fictional maintenance item clears the demonstration gate.",
        },
        "discard_summary": {"count": 0, "reasons": []},
    }
    return {
        "schema_version": "demo-1.0",
        "mode": "standalone_fictional_contract_demo",
        "demo_only": True,
        "kernel_exercised": False,
        "companion_kernel_required_for_live": True,
        "network_required": False,
        "account_required": False,
        "install_required": False,
        "action_executed": False,
        "receipt_persisted": False,
        "source_health": [
            {
                "name": "fictional-local-feed",
                "status": "healthy",
                "items_seen": 3,
                "items_valid": 3,
                "errors": [],
            }
        ],
        "counts": {
            "normalized": 3,
            "deduplicated": 3,
            "excluded_as_processed": 0,
            "excluded_from_stale_sources": 0,
            "shortlisted": 3,
        },
        "worth_knowing_count": 3,
        "worth_knowing": worth_knowing,
        "formal_promotion_count": 1,
        "selected": {
            "id": "demo_cache_change",
            "title": "Fictional cache policy changes next week",
            "source": "fictional-local-feed",
            "proposed_dispositions": ["act"],
        },
        "round_review": round_review,
        "receipt_id": receipt_id,
    }


def _render_human(payload: dict[str, Any]) -> str:
    counts = payload["counts"]
    health = payload["source_health"]
    healthy = sum(row.get("status") == "healthy" for row in health)
    selected = payload["selected"]
    lines = [
        "X Signal Digest — offline fictional demo",
        "No account · no key · no network · no external action",
        "",
        f"Sources healthy:     {healthy}/{len(health)}",
        f"Items normalized:    {counts['normalized']}",
        f"Items deduplicated:  {counts['deduplicated']}",
        f"Semantic shortlist:  {counts['shortlisted']}",
        f"Worth knowing:       {payload['worth_knowing_count']}",
        f"Formal promotions:   {payload['formal_promotion_count']}",
        "",
    ]
    for entry in payload["worth_knowing"]:
        lines.append(f"Worth knowing: {entry['title']} [{entry['evidence_status']}]")
    lines.extend(
        [
            "",
            f"Formally promoted (demo only): {selected['title']}",
            "Proposed disposition: "
            + (", ".join(selected.get("proposed_dispositions", [])) or "none")
            + " (not executed)",
            f"Demo receipt: {payload['receipt_id']} (not persisted)",
            "",
        ]
    )
    if payload["kernel_exercised"]:
        lines.append("The companion deterministic kernel was exercised in isolated temporary state.")
    else:
        lines.append("This standalone run demonstrates the report contract; install the companion CLI for live feeds.")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    parser.add_argument(
        "--portable",
        action="store_true",
        help="force the standalone contract demo even when the companion checkout is present",
    )
    args = parser.parse_args(argv)

    try:
        demo = None if args.portable else _adjacent_demo()
        payload = _kernel_payload(demo) if demo else _portable_payload()
    except (OSError, RuntimeError, json.JSONDecodeError) as exc:
        print(f"x-signal-digest: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        sys.stdout.write(_render_human(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
