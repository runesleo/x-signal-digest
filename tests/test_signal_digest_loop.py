from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "src"))

from signal_digest_loop.config import ConfigError, load_settings  # noqa: E402
from signal_digest_loop.decisions import no_signal_decision, validate_decision  # noqa: E402
from signal_digest_loop.engine import (  # noqa: E402
    commit_decision,
    create_digest,
    digest_markdown,
    prepare_packet,
    run_command_analyzer,
    run_cycle,
    submit_feedback,
)
from signal_digest_loop.errors import ContractError  # noqa: E402


NOW = datetime(2026, 8, 2, 12, 0, tzinfo=timezone.utc)


class SignalDigestLoopTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.source = self.root / "feed.json"
        self.config = self.root / "signal-digest.toml"

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def write_source(self, items: list[dict], path: Path | None = None) -> Path:
        target = path or self.source
        target.write_text(json.dumps({"items": items}), encoding="utf-8")
        os.utime(target, (NOW.timestamp(), NOW.timestamp()))
        return target

    def write_config(
        self,
        *,
        sources: str | None = None,
        analyzer: str = "",
        threshold: float = 0.1,
        limits: str = "",
    ) -> None:
        source_tables = sources or """
[[sources]]
name = "feed"
type = "json"
path = "feed.json"
items_path = "items"
weight = 1.0
freshness_hours = 24

[sources.fields]
title = "title"
url = "url"
text = "text"
published_at = "published_at"
engagement = "engagement"
"""
        self.config.write_text(
            f"""state_dir = ".state"
timezone = "UTC"

[loop]
shortlist_limit = 5
promotion_threshold = {threshold}
processed_ttl_hours = 336
feedback_min_multiplier = 0.5
feedback_max_multiplier = 1.5
feedback_step = 0.05
feedback_max_step = 0.2

[limits]
{limits}

[analyzer]
{analyzer}
timeout_seconds = 5

{source_tables}
""",
            encoding="utf-8",
        )

    @staticmethod
    def decision(packet: dict, candidate_id: str | None = None) -> dict:
        selected = candidate_id or packet["shortlist"][0]["id"]
        candidate = next(item for item in packet["shortlist"] if item["id"] == selected)
        return {
            "schema_version": "1.0",
            "packet_id": packet["packet_id"],
            "selection": selected,
            "claims": [
                {
                    "statement": "The synthetic source announces a reversible change.",
                    "evidence": ["https://example.invalid/change"],
                }
            ],
            "relation": {
                "summary": "The item may change a maintenance decision.",
                "targets": ["maintenance_review"],
            },
            "memory_check": {"status": "new", "notes": "No synthetic prior hit."},
            "knowledge_delta": {
                "summary": "A new fictional maintenance constraint.",
                "novelty": "medium",
            },
            "dispositions": [
                {
                    "type": "learn",
                    "route": "knowledge_note",
                    "rationale": "The constraint is reusable.",
                    "next_action": "Record the synthetic lesson.",
                }
            ],
            "timeliness": {
                "status": "soon",
                "expires_at": "2026-08-09T00:00:00Z",
            },
            "effort": {"level": "low", "estimate": "15 minutes"},
            "gates": [],
            "round_review": {
                "schema_version": "1.0",
                "worth_knowing": [
                    {
                        "candidate_id": selected,
                        "title": candidate["title"],
                        "source_ref": candidate.get("url") or candidate["source"],
                        "why_it_matters": "It may affect a maintenance decision.",
                        "evidence_status": "attributed_unverified",
                        "evidence_boundary": "Synthetic source only.",
                        "utilization_angles": [
                            {
                                "angle": "workflow",
                                "fit": "now",
                                "suggestion": "Review the synthetic change.",
                            }
                        ],
                    }
                ],
                "formal_selection": {
                    "count": 1,
                    "selected_id": selected,
                    "summary": "One synthetic change clears the formal gate.",
                },
                "discard_summary": {
                    "count": len(packet["shortlist"]) - 1,
                    "reasons": (
                        [] if len(packet["shortlist"]) == 1 else ["Not worth knowing this round."]
                    ),
                },
            },
        }

    @staticmethod
    def review_entry(candidate: dict, *, index: int = 0) -> dict:
        return {
            "candidate_id": candidate["id"],
            "title": candidate["title"],
            "source_ref": candidate.get("url") or candidate["source"],
            "why_it_matters": f"Synthetic awareness item {index + 1}.",
            "evidence_status": "attributed_unverified",
            "evidence_boundary": "Only the fictional packet artifact was inspected.",
            "utilization_angles": [
                {
                    "angle": ("business", "research", "learning")[index % 3],
                    "fit": "now" if index == 0 else "later",
                    "suggestion": f"Use synthetic item {index + 1} in the stated context.",
                }
            ],
        }

    def four_item_packet(self) -> tuple[object, dict]:
        self.write_source(
            [
                {
                    "title": f"Synthetic candidate {index}",
                    "text": "Maintenance context",
                    "url": f"https://example.invalid/candidate-{index}",
                    "published_at": "2026-08-02T11:00:00Z",
                    "engagement": 100 - index,
                }
                for index in range(4)
            ]
        )
        self.write_config()
        settings = load_settings(self.config)
        return settings, prepare_packet(settings, now=NOW)

    def three_to_one_decision(self, packet: dict) -> dict:
        decision = self.decision(packet)
        decision["round_review"] = {
            "schema_version": "1.0",
            "worth_knowing": [
                self.review_entry(candidate, index=index)
                for index, candidate in enumerate(packet["shortlist"][:3])
            ],
            "formal_selection": {
                "count": 1,
                "selected_id": decision["selection"],
                "summary": "One of three awareness items clears the formal gate.",
            },
            "discard_summary": {
                "count": len(packet["shortlist"]) - 3,
                "reasons": ["The remaining candidate was below the awareness cutoff."],
            },
        }
        return decision

    def test_prepare_tracks_health_deduplicates_and_redacts_absolute_paths(self) -> None:
        stale = self.root / "stale.json"
        item = {
            "title": "Synthetic change",
            "text": "A reversible maintenance change.",
            "url": "https://example.invalid/change?utm_source=test",
            "published_at": "2026-08-02T11:00:00Z",
            "engagement": 100,
        }
        self.write_source([item, {**item, "url": "https://example.invalid/change"}])
        self.write_source([{**item, "url": "https://example.invalid/stale"}], stale)
        old = (NOW - timedelta(days=3)).timestamp()
        os.utime(stale, (old, old))
        self.write_config(
            sources="""
[[sources]]
name = "fresh"
type = "json"
path = "feed.json"
freshness_hours = 24

[sources.fields]
title = "title"
url = "url"
text = "text"
published_at = "published_at"
engagement = "engagement"

[[sources]]
name = "stale"
type = "json"
path = "stale.json"
freshness_hours = 24

[sources.fields]
title = "title"
url = "url"
text = "text"
published_at = "published_at"
engagement = "engagement"
"""
        )
        packet = prepare_packet(load_settings(self.config), now=NOW)
        health = {row["name"]: row["status"] for row in packet["source_health"]}
        self.assertEqual(health, {"fresh": "healthy", "stale": "stale"})
        self.assertEqual(len(packet["shortlist"]), 1)
        self.assertEqual(packet["shortlist"][0]["url"], "https://example.invalid/change")
        self.assertEqual(packet["counts"]["excluded_from_stale_sources"], 1)
        serialized = json.dumps(packet)
        self.assertNotIn(str(self.root), serialized)

    def test_decision_is_packet_bound_and_strictly_zero_or_one(self) -> None:
        self.write_source(
            [
                {
                    "title": "Synthetic change",
                    "text": "Maintenance",
                    "url": "https://example.invalid/change",
                    "published_at": "2026-08-02T11:00:00Z",
                }
            ]
        )
        self.write_config()
        settings = load_settings(self.config)
        packet = prepare_packet(settings, now=NOW)
        bad = self.decision(packet)
        bad["packet_id"] = "pkt_other"
        with self.assertRaisesRegex(ContractError, "packet_id"):
            commit_decision(settings, packet, bad, now=NOW)
        bad = self.decision(packet)
        bad["selection"] = [packet["shortlist"][0]["id"], "another"]
        with self.assertRaises(ContractError):
            commit_decision(settings, packet, bad, now=NOW)

    def test_null_selection_is_a_strict_fail_closed_abstention(self) -> None:
        self.write_source(
            [
                {
                    "title": "Synthetic change",
                    "text": "Maintenance",
                    "url": "https://example.invalid/change",
                    "published_at": "2026-08-02T11:00:00Z",
                }
            ]
        )
        self.write_config()
        packet = prepare_packet(load_settings(self.config), now=NOW)
        baseline = no_signal_decision(packet, "No decision-changing evidence.")
        self.assertIsNone(validate_decision(baseline, packet)["selection"])

        invalid_cases: list[tuple[str, dict]] = []
        changed = deepcopy(baseline)
        changed["claims"] = [{"statement": "Unbound claim", "evidence": ["synthetic"]}]
        invalid_cases.append(("claims", changed))
        changed = deepcopy(baseline)
        changed["dispositions"] = [
            {"type": "act", "route": "execution", "rationale": "Hidden action"}
        ]
        invalid_cases.append(("dispositions", changed))
        changed = deepcopy(baseline)
        changed["relation"]["targets"] = ["hidden_target"]
        invalid_cases.append(("relation.targets", changed))
        changed = deepcopy(baseline)
        changed["knowledge_delta"]["novelty"] = "high"
        invalid_cases.append(("knowledge_delta", changed))
        changed = deepcopy(baseline)
        changed["timeliness"] = {"status": "soon", "expires_at": None}
        invalid_cases.append(("timeliness.status", changed))
        changed = deepcopy(baseline)
        changed["timeliness"]["expires_at"] = "2026-08-03T00:00:00Z"
        invalid_cases.append(("timeliness.expires_at", changed))
        changed = deepcopy(baseline)
        changed["effort"] = {"level": "low", "estimate": "5 minutes"}
        invalid_cases.append(("effort.level", changed))

        for label, decision in invalid_cases:
            with self.subTest(label=label), self.assertRaisesRegex(ContractError, "selection=null"):
                validate_decision(decision, packet)

    def test_round_review_valid_three_to_one_is_mirrored_in_receipt(self) -> None:
        settings, packet = self.four_item_packet()
        decision = self.three_to_one_decision(packet)

        validated = validate_decision(decision, packet)
        self.assertEqual(len(validated["round_review"]["worth_knowing"]), 3)
        receipt = commit_decision(settings, packet, decision, now=NOW)
        self.assertEqual(receipt["round_review"], decision["round_review"])
        self.assertEqual(receipt["round_review"]["formal_selection"]["count"], 1)

        digest = create_digest(settings, date="2026-08-02")
        self.assertEqual(digest["round_review_count"], 1)
        self.assertEqual(digest["worth_knowing_count"], 3)
        self.assertEqual(len(digest["worth_knowing_entries"]), 3)
        self.assertEqual(sum(item["formal_selected"] for item in digest["worth_knowing_entries"]), 1)
        self.assertEqual(digest["promotion_count"], 1)
        self.assertEqual(len(digest["entries"]), 1)
        first_awareness = digest["worth_knowing_entries"][0]
        self.assertEqual(first_awareness["receipt_id"], receipt["receipt_id"])
        self.assertEqual(first_awareness["packet_id"], packet["packet_id"])
        markdown = digest_markdown(digest)
        self.assertIn("- Worth knowing: 3", markdown)
        self.assertIn("## Worth knowing", markdown)
        self.assertIn("## Formal selections", markdown)
        self.assertIn("Evidence status: attributed\\_unverified", markdown)
        self.assertIn("Utilization (business, now)", markdown)

    def test_round_review_allows_worth_knowing_with_null_formal_selection(self) -> None:
        settings, packet = self.four_item_packet()
        reason = "Useful context exists, but none changes a formal decision."
        awareness = [
            self.review_entry(candidate, index=index)
            for index, candidate in enumerate(packet["shortlist"][:2])
        ]
        decision = no_signal_decision(
            packet,
            reason,
            worth_knowing=awareness,
            discard_reasons=["Two candidates did not clear the awareness cutoff."],
        )

        validated = validate_decision(decision, packet)
        self.assertIsNone(validated["selection"])
        self.assertEqual(len(validated["round_review"]["worth_knowing"]), 2)
        self.assertEqual(validated["round_review"]["discard_summary"]["count"], 2)

        receipt = commit_decision(settings, packet, decision, now=NOW)
        digest = create_digest(settings, date="2026-08-02")
        self.assertEqual(digest["round_review_count"], 1)
        self.assertEqual(digest["worth_knowing_count"], 2)
        self.assertEqual(digest["promotion_count"], 0)
        self.assertEqual(digest["entries"], [])
        self.assertTrue(all(not item["formal_selected"] for item in digest["worth_knowing_entries"]))
        self.assertEqual(digest["worth_knowing_entries"][0]["receipt_id"], receipt["receipt_id"])
        markdown = digest_markdown(digest)
        self.assertIn("- Worth knowing: 2", markdown)
        self.assertIn("## Worth knowing", markdown)
        self.assertNotIn("## Formal selections", markdown)
        self.assertIn("Evidence boundary:", markdown)

    def test_round_review_rejects_unbound_duplicate_mismatched_and_invalid_fields(self) -> None:
        _, packet = self.four_item_packet()
        baseline = self.three_to_one_decision(packet)
        cases: list[tuple[str, dict, str]] = []

        changed = deepcopy(baseline)
        changed["round_review"]["formal_selection"]["count"] = 0
        cases.append(("formal count", changed, "must match top-level selection"))
        changed = deepcopy(baseline)
        changed["round_review"]["formal_selection"]["selected_id"] = packet["shortlist"][1]["id"]
        cases.append(("formal id", changed, "must match top-level selection"))
        changed = deepcopy(baseline)
        changed["round_review"]["worth_knowing"][0]["candidate_id"] = "sig_unknown"
        cases.append(("unknown id", changed, "not present in packet.shortlist"))
        changed = deepcopy(baseline)
        changed["round_review"]["worth_knowing"][1] = deepcopy(
            changed["round_review"]["worth_knowing"][0]
        )
        cases.append(("duplicate id", changed, "must be unique"))
        changed = deepcopy(baseline)
        changed["round_review"]["worth_knowing"][0]["title"] = "Invented title"
        cases.append(("title mismatch", changed, "title must exactly match"))
        changed = deepcopy(baseline)
        changed["round_review"]["worth_knowing"][0]["source_ref"] = "invented-source"
        cases.append(("source mismatch", changed, "source_ref must exactly match"))
        changed = deepcopy(baseline)
        changed["round_review"]["discard_summary"]["count"] = 0
        cases.append(("reconciliation", changed, "must reconcile"))
        changed = deepcopy(baseline)
        changed["round_review"]["worth_knowing"][0]["evidence_status"] = "probably_true"
        cases.append(("evidence enum", changed, "evidence_status must be one of"))
        changed = deepcopy(baseline)
        changed["round_review"]["worth_knowing"][0]["utilization_angles"][0]["angle"] = "sales"
        cases.append(("angle enum", changed, ".angle must be one of"))
        changed = deepcopy(baseline)
        changed["round_review"]["worth_knowing"][0]["utilization_angles"][0]["fit"] = "maybe"
        cases.append(("fit enum", changed, ".fit must be one of"))
        changed = deepcopy(baseline)
        changed["round_review"]["worth_knowing"][0]["extra"] = "not allowed"
        cases.append(("exact fields", changed, "unknown extra"))

        for label, decision, message in cases:
            with self.subTest(label=label), self.assertRaisesRegex(ContractError, message):
                validate_decision(decision, packet)

    def test_commit_is_idempotent_and_processed_items_are_suppressed(self) -> None:
        self.write_source(
            [
                {
                    "title": "Synthetic change",
                    "text": "Maintenance",
                    "url": "https://example.invalid/change",
                    "published_at": "2026-08-02T11:00:00Z",
                }
            ]
        )
        self.write_config()
        settings = load_settings(self.config)
        packet = prepare_packet(settings, now=NOW)
        decision = self.decision(packet)
        first = commit_decision(settings, packet, decision, now=NOW)
        state_before = (settings.state_dir / "state.json").read_bytes()
        second = commit_decision(settings, packet, decision, now=NOW + timedelta(hours=2))
        self.assertEqual(first, second)
        self.assertEqual(state_before, (settings.state_dir / "state.json").read_bytes())
        next_packet = prepare_packet(settings, now=NOW + timedelta(hours=3))
        self.assertEqual(next_packet["shortlist"], [])

    def test_zero_cycle_and_digest_use_commit_receipts(self) -> None:
        self.write_source(
            [
                {
                    "title": "Synthetic hello",
                    "text": "No action.",
                    "url": "https://example.invalid/hello",
                    "published_at": "2026-08-02T11:00:00Z",
                }
            ]
        )
        self.write_config()
        settings = load_settings(self.config)
        result = run_cycle(settings, apply=True, now=NOW)
        self.assertEqual(result["receipt"]["selection"], None)
        digest = create_digest(settings, date="2026-08-02")
        self.assertEqual(digest["receipt_count"], 1)
        self.assertEqual(digest["promotion_count"], 0)
        self.assertEqual(digest["no_signal_count"], 1)

    def test_command_analyzer_requires_opt_in_and_does_not_use_a_shell(self) -> None:
        self.write_source(
            [
                {
                    "title": "Synthetic change",
                    "text": "Maintenance",
                    "url": "https://example.invalid/change",
                    "published_at": "2026-08-02T11:00:00Z",
                }
            ]
        )
        analyzer = self.root / "analyzer.py"
        analyzer.write_text(
            "import json,sys\n"
            "p=json.load(sys.stdin)\n"
            "d={\"schema_version\":\"1.0\",\"packet_id\":p[\"packet_id\"],"
            "\"selection\":None,\"no_signal_reason\":\"Synthetic abstention.\","
            "\"claims\":[],\"relation\":{\"summary\":\"\",\"targets\":[]},"
            "\"memory_check\":{\"status\":\"not_checked\",\"notes\":\"\"},"
            "\"knowledge_delta\":{\"summary\":\"\",\"novelty\":\"none\"},"
            "\"dispositions\":[],\"timeliness\":{\"status\":\"expired\",\"expires_at\":None},"
            "\"effort\":{\"level\":\"none\",\"estimate\":\"\"},\"gates\":[],"
            "\"round_review\":{\"schema_version\":\"1.0\",\"worth_knowing\":[],"
            "\"formal_selection\":{\"count\":0,\"selected_id\":None,"
            "\"summary\":\"Synthetic abstention.\"},\"discard_summary\":{\"count\":len(p[\"shortlist\"]),"
            "\"reasons\":[\"Not worth knowing.\"] if p[\"shortlist\"] else []}}}\n"
            "json.dump(d,sys.stdout)\n",
            encoding="utf-8",
        )
        self.write_config(analyzer=f'command = [{json.dumps(sys.executable)}, "analyzer.py"]')
        settings = load_settings(self.config)
        with self.assertRaisesRegex(ContractError, "explicitly allow"):
            run_cycle(settings, now=NOW)
        result = run_cycle(settings, allow_command_analyzer=True, now=NOW)
        self.assertEqual(result["status"], "dry_run")
        self.assertFalse((settings.state_dir / "receipts" / "commits").exists())

        marker = self.root / "shell-marker"
        packet = result["packet"]
        with self.assertRaises(ContractError):
            run_command_analyzer(
                packet,
                [sys.executable, "-c", "import sys;sys.exit(0)", f";touch {marker}"],
                timeout_seconds=2,
                working_directory=self.root,
            )
        self.assertFalse(marker.exists())

    def test_analyzer_command_rejects_shell_strings(self) -> None:
        self.write_source([])
        self.write_config(analyzer='command = "python analyzer.py"')
        with self.assertRaisesRegex(ConfigError, "array of strings"):
            load_settings(self.config)

    def test_feedback_is_previewable_bounded_and_reversible(self) -> None:
        self.write_source([])
        self.write_config()
        settings = load_settings(self.config)
        preview = submit_feedback(settings, source="feed", outcome="positive", apply=False, now=NOW)
        self.assertEqual(preview["status"], "preview")
        self.assertFalse((settings.state_dir / "state.json").exists())
        applied = submit_feedback(settings, source="feed", outcome="positive", apply=True, now=NOW)
        self.assertEqual(applied["new_multiplier"], 1.05)
        undone = submit_feedback(
            settings,
            undo_receipt_id=applied["receipt_id"],
            apply=True,
            now=NOW + timedelta(minutes=1),
        )
        self.assertEqual(undone["new_multiplier"], 1.0)

    def test_oversized_json_and_markdown_sources_fail_closed(self) -> None:
        markdown = self.root / "notes.md"
        self.write_source(
            [{"title": "Oversized JSON", "text": "x" * 2_000}], self.source
        )
        markdown.write_text("# Oversized Markdown\n\n" + "x" * 2_000, encoding="utf-8")
        os.utime(markdown, (NOW.timestamp(), NOW.timestamp()))
        self.write_config(
            limits="max_source_bytes = 1024",
            sources="""
[[sources]]
name = "json"
type = "json"
path = "feed.json"

[[sources]]
name = "markdown"
type = "markdown"
path = "notes.md"
""",
        )
        packet = prepare_packet(load_settings(self.config), now=NOW)
        self.assertEqual(packet["shortlist"], [])
        for health in packet["source_health"]:
            self.assertEqual(health["status"], "invalid")
            self.assertEqual(health["limit_exceeded"], "max_source_bytes")

    def test_jsonl_line_row_and_error_limits_fail_closed(self) -> None:
        source = self.root / "feed.jsonl"
        cases = [
            (
                "line",
                json.dumps({"title": "x" * 200}) + "\n",
                "max_rows = 10\nmax_line_bytes = 128\nmax_errors = 2",
                "max_line_bytes",
            ),
            (
                "rows",
                "\n".join(json.dumps({"title": f"row-{index}"}) for index in range(3)) + "\n",
                "max_rows = 2\nmax_line_bytes = 1024\nmax_errors = 2",
                "max_rows",
            ),
            (
                "errors",
                "not-json\nstill-not-json\n",
                "max_rows = 5\nmax_line_bytes = 1024\nmax_errors = 1",
                "max_errors",
            ),
        ]
        for label, content, limits, expected in cases:
            with self.subTest(label=label):
                source.write_text(content, encoding="utf-8")
                os.utime(source, (NOW.timestamp(), NOW.timestamp()))
                self.write_config(
                    limits=limits,
                    sources="""
[[sources]]
name = "feed"
type = "jsonl"
path = "feed.jsonl"
freshness_hours = 24
""",
                )
                packet = prepare_packet(load_settings(self.config), now=NOW)
                self.assertEqual(packet["shortlist"], [])
                health = packet["source_health"][0]
                self.assertEqual(health["status"], "invalid")
                self.assertIn(expected, " ".join(health["errors"]))

    def test_global_row_budget_and_engagement_depth_bound_normalization(self) -> None:
        second = self.root / "second.json"
        self.write_source(
            [
                {
                    "title": "Allowed row",
                    "url": "https://example.invalid/allowed",
                    "published_at": "2026-08-02T11:00:00Z",
                    "engagement": {"a": {"b": {"c": 1_000_000}}},
                }
            ]
        )
        self.write_source(
            [
                {"title": "Over budget one", "url": "https://example.invalid/one"},
                {"title": "Over budget two", "url": "https://example.invalid/two"},
            ],
            second,
        )
        self.write_config(
            limits="max_rows = 2\nmax_engagement_depth = 2",
            sources="""
[[sources]]
name = "first"
type = "json"
path = "feed.json"

[sources.fields]
title = "title"
url = "url"
published_at = "published_at"
engagement = "engagement"

[[sources]]
name = "second"
type = "json"
path = "second.json"
""",
        )
        packet = prepare_packet(load_settings(self.config), now=NOW)
        self.assertEqual(packet["counts"]["normalized"], 1)
        self.assertEqual(len(packet["shortlist"]), 1)
        self.assertEqual(packet["shortlist"][0]["score_components"]["engagement"], 0.0)
        second_health = packet["source_health"][1]
        self.assertEqual(second_health["status"], "invalid")
        self.assertIn("max_rows", " ".join(second_health["errors"]))


class PublicReleasePrivacyTests(unittest.TestCase):
    def test_agent_skill_preflight_redacts_profile_and_paths(self) -> None:
        script = PROJECT / "skills" / "x-signal-digest" / "scripts" / "preflight.py"
        completed = subprocess.run(
            [
                sys.executable,
                str(script),
                "--mode",
                "live",
                "--profile",
                "SECRET_PROFILE_LABEL",
                "--collector-command",
                "missing-demo-collector",
                "--json",
            ],
            cwd=PROJECT,
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(completed.returncode, 2)
        payload = json.loads(completed.stdout)
        self.assertTrue(payload["account_boundary"]["profile_declared"])
        self.assertNotIn("profile_label", payload["account_boundary"])
        self.assertNotIn("SECRET_PROFILE_LABEL", completed.stdout)
        self.assertNotIn("paths", payload)

    def test_agent_skill_portable_demo_needs_no_parent_kernel(self) -> None:
        script = PROJECT / "skills" / "x-signal-digest" / "scripts" / "run_demo.py"
        completed = subprocess.run(
            [sys.executable, str(script), "--portable", "--json"],
            cwd=PROJECT,
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["mode"], "standalone_fictional_contract_demo")
        self.assertFalse(payload["kernel_exercised"])
        self.assertFalse(payload["network_required"])
        self.assertFalse(payload["account_required"])
        self.assertFalse(payload["action_executed"])
        self.assertFalse(payload["receipt_persisted"])
        self.assertEqual(payload["worth_knowing_count"], 3)
        self.assertEqual(payload["formal_promotion_count"], 1)

    def test_one_command_demo_is_offline_and_machine_readable(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(PROJECT / "demo.py"), "--json"],
            cwd=PROJECT,
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["mode"], "offline_fictional_sample")
        self.assertFalse(payload["network_required"])
        self.assertFalse(payload["account_required"])
        self.assertFalse(payload["install_required"])
        self.assertEqual(payload["time_to_first_digest_target_seconds"], 180)
        self.assertEqual(payload["formal_promotion_count"], 1)
        self.assertEqual(payload["worth_knowing_count"], 3)
        self.assertEqual(payload["round_review"]["formal_selection"]["count"], 1)
        self.assertTrue(payload["receipt_id"])

    def test_xreach_adapter_maps_fictional_export_to_kernel_rows(self) -> None:
        adapter = PROJECT / "examples" / "adapters" / "xreach_to_jsonl.py"
        completed = subprocess.run(
            [sys.executable, str(adapter), str(adapter.parent / "fictional_xreach_export.json")],
            capture_output=True, text=True, check=True,
        )
        rows = [json.loads(line) for line in completed.stdout.splitlines()]
        self.assertEqual(len(rows), 1, "retweets are skipped by default")
        row = rows[0]
        self.assertEqual(row["url"], "https://x.com/example_lab/status/1000000000000000001")
        self.assertEqual(row["published_at"], "2026-10-19T08:00:00Z")
        self.assertEqual(sum(row["engagement"].values()), 22)
        self.assertTrue(row["title"].startswith("@example_lab: Fictional lab"))

    def test_xreach_adapter_rejects_error_payload_without_touching_output(self) -> None:
        adapter = PROJECT / "examples" / "adapters" / "xreach_to_jsonl.py"
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "signals.jsonl"
            out.write_text("previous\n", encoding="utf-8")
            completed = subprocess.run(
                [sys.executable, str(adapter), "-", "--output", str(out)],
                input='{"error": "rate limited"}', capture_output=True, text=True, check=False,
            )
            self.assertEqual(completed.returncode, 2)
            self.assertEqual(out.read_text(encoding="utf-8"), "previous\n")

    def test_preflight_has_no_private_search_default(self) -> None:
        script = PROJECT / "skills" / "x-signal-digest" / "scripts" / "preflight.py"
        completed = subprocess.run(
            [sys.executable, str(script), "--mode", "live", "--profile", "LABEL",
             "--collector-command", sys.executable, "--json"],
            capture_output=True, text=True, check=False,
        )
        names = [row["name"] for row in json.loads(completed.stdout)["checks"]]
        self.assertNotIn("active_search_helper", names)

    def test_public_tree_contains_no_private_instance_strings(self) -> None:
        forbidden = ["/" + "Users/", "/" + "home/"]
        # Instance-specific strings (usernames, profile names, private tool names)
        # stay out of the public tree: put them one per line in a local file and
        # point SIGNAL_DIGEST_PRIVATE_DENYLIST at it before running the tests.
        denylist = os.environ.get("SIGNAL_DIGEST_PRIVATE_DENYLIST")
        if denylist and Path(denylist).is_file():
            forbidden += [
                line.strip()
                for line in Path(denylist).read_text(encoding="utf-8").splitlines()
                if line.strip() and not line.startswith("#")
            ]
        for path in PROJECT.rglob("*"):
            if (
                not path.is_file()
                or any(part in {".git", ".state", "__pycache__"} for part in path.parts)
                or path.suffix == ".pyc"
            ):
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            for needle in forbidden:
                self.assertNotIn(needle, text, f"{needle!r} leaked in {path}")


if __name__ == "__main__":
    unittest.main()
