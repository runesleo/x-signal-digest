#!/usr/bin/env python3
"""Run the fictional Signal Digest Loop sample with no install or network."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any


PROJECT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT / "src"))

from signal_digest_loop.config import load_settings  # noqa: E402
from signal_digest_loop.engine import create_digest, run_cycle  # noqa: E402


def _copy_sample(target: Path) -> Path:
    """Create a fresh, isolated copy so repeated demos never share state."""

    source_root = PROJECT / "examples"
    (target / "sources").mkdir(parents=True)
    for relative in (
        Path("config.toml"),
        Path("rule_based_analyzer.py"),
        Path("sources/fictional_feed.json"),
    ):
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_root / relative, destination)
    return target / "config.toml"


def _summary(result: dict[str, Any], digest: dict[str, Any]) -> dict[str, Any]:
    packet = result["packet"]
    decision = result["decision"]
    selection = decision.get("selection")
    selected = next(
        (item for item in packet["shortlist"] if item.get("id") == selection),
        None,
    )
    receipt = result.get("receipt") or {}
    round_review = decision["round_review"]
    dispositions = [
        item.get("type")
        for item in decision.get("dispositions", [])
        if isinstance(item, dict) and item.get("type")
    ]
    return {
        "schema_version": "demo-1.0",
        "mode": "offline_fictional_sample",
        "network_required": False,
        "account_required": False,
        "install_required": False,
        "time_to_first_digest_target_seconds": 180,
        "source_health": packet["source_health"],
        "counts": packet["counts"],
        "formal_promotion_count": digest["promotion_count"],
        "worth_knowing_count": len(round_review["worth_knowing"]),
        "worth_knowing": round_review["worth_knowing"],
        "round_review": receipt.get("round_review"),
        "selected": {
            "id": selection,
            "title": selected.get("title") if selected else None,
            "source": selected.get("source") if selected else None,
            "dispositions": dispositions,
        },
        "receipt_id": receipt.get("receipt_id"),
        "digest": digest,
    }


def _render_human(payload: dict[str, Any]) -> str:
    counts = payload["counts"]
    selected = payload["selected"]
    health = payload["source_health"]
    healthy = sum(row.get("status") == "healthy" for row in health)
    lines = [
        "Signal Digest Loop — offline sample",
        "No install · no account · no key · no network",
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
        lines.append(
            f"Worth knowing: {entry['title']} [{entry['evidence_status']}]"
        )
    lines.append("")
    if selected["id"]:
        lines.extend(
            [
                f"Selected: {selected['title']}",
                f"Route:    {', '.join(selected['dispositions']) or 'unspecified'}",
                f"Receipt:  {payload['receipt_id']}",
            ]
        )
    else:
        lines.append("Selected: none — zero is a valid result")
    lines.extend(
        [
            "",
            "This run used fictional local data and an isolated temporary state directory.",
        ]
    )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit the sample summary as JSON")
    arguments = parser.parse_args(argv)

    with tempfile.TemporaryDirectory(prefix="signal-digest-loop-demo-") as temporary:
        config_path = _copy_sample(Path(temporary))
        settings = load_settings(config_path)
        result = run_cycle(
            settings,
            allow_command_analyzer=True,
            apply=True,
        )
        payload = _summary(result, create_digest(settings))

    if arguments.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        sys.stdout.write(_render_human(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
