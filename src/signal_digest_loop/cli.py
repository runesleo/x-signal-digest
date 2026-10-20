"""Command-line interface for Signal Digest Loop."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from . import __version__
from .config import DEFAULT_CONFIG, load_settings
from .engine import (
    commit_decision,
    create_digest,
    digest_markdown,
    prepare_packet,
    run_cycle,
    submit_feedback,
)
from .errors import SignalDigestError
from .storage import atomic_write_text


def _common_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument(
        "-c",
        "--config",
        default="signal-digest.toml",
        help="TOML configuration path (default: signal-digest.toml)",
    )
    return parser


def build_parser() -> argparse.ArgumentParser:
    """Build the public argument parser."""

    parser = argparse.ArgumentParser(
        prog="signal-digest",
        description="Offline-first prepare → analyze → commit information digestion loop.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subcommands = parser.add_subparsers(dest="command", required=True)
    common = _common_parser()

    initialize = subcommands.add_parser(
        "init",
        help="write a safe starter TOML configuration",
        description="Create a starter configuration. Existing files are preserved unless --force is set.",
    )
    initialize.add_argument("path", nargs="?", default="signal-digest.toml")
    initialize.add_argument("--force", action="store_true", help="replace an existing config file")

    prepare = subcommands.add_parser(
        "prepare",
        parents=[common],
        help="health-check, normalize, deduplicate, and rank local inputs",
    )
    prepare.add_argument(
        "--output",
        help="also write the emitted packet JSON to this path ('-' keeps stdout only)",
    )

    commit = subcommands.add_parser(
        "commit",
        parents=[common],
        help="validate a decision and atomically record its receipt/state",
    )
    commit.add_argument(
        "--packet",
        default="latest",
        help="packet id or JSON path (default: latest)",
    )
    commit.add_argument(
        "--decision",
        required=True,
        help="decision JSON path, or '-' to read JSON from stdin",
    )

    cycle = subcommands.add_parser(
        "cycle",
        parents=[common],
        help="prepare and analyze one dry-safe automatic cycle",
        description=(
            "Prepare one packet and optionally invoke the configured command analyzer. "
            "No decision receipt or processed state is written unless --apply is present."
        ),
    )
    cycle.add_argument(
        "--allow-command-analyzer",
        action="store_true",
        help="explicitly allow the configured external analyzer for this invocation",
    )
    cycle.add_argument(
        "--apply",
        action="store_true",
        help="commit the validated zero-or-one decision (default: dry run)",
    )

    digest = subcommands.add_parser(
        "digest",
        parents=[common],
        help="summarize immutable commit receipts",
    )
    digest.add_argument("--date", help="optional UTC receipt date in YYYY-MM-DD form")
    digest.add_argument("--format", choices=("json", "markdown"), default="json")
    digest.add_argument("--output", help="write rendered output to a file instead of stdout")

    feedback = subcommands.add_parser(
        "feedback",
        parents=[common],
        help="preview or apply a bounded, reversible source-weight update",
    )
    feedback.add_argument("--source", help="configured source name")
    feedback.add_argument("--outcome", choices=("positive", "negative", "neutral"))
    feedback.add_argument("--amount", type=float, help="bounded adjustment step")
    feedback.add_argument("--undo", metavar="RECEIPT_ID", help="undo the latest-compatible feedback receipt")
    feedback.add_argument(
        "--apply",
        action="store_true",
        help="persist the update and receipt (default: preview)",
    )
    return parser


def _read_decision(path: str) -> dict[str, Any]:
    try:
        if path == "-":
            payload = json.load(sys.stdin)
        else:
            with Path(path).expanduser().open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise SignalDigestError(f"cannot read decision JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise SignalDigestError("decision JSON root must be an object")
    return payload


def _json_text(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _emit(text: str, output: str | None = None) -> None:
    if output and output != "-":
        atomic_write_text(Path(output).expanduser().resolve(), text)
    else:
        sys.stdout.write(text)


def main(argv: list[str] | None = None) -> int:
    """Execute a CLI command and return its process exit status."""

    parser = build_parser()
    arguments = parser.parse_args(argv)
    try:
        if arguments.command == "init":
            target = Path(arguments.path).expanduser().resolve()
            if target.exists() and not arguments.force:
                raise SignalDigestError(f"configuration already exists: {target}")
            atomic_write_text(target, DEFAULT_CONFIG)
            _emit(_json_text({"status": "initialized", "config": str(target)}))
            return 0

        settings = load_settings(arguments.config)
        if arguments.command == "prepare":
            packet = prepare_packet(settings)
            _emit(_json_text(packet), arguments.output)
        elif arguments.command == "commit":
            receipt = commit_decision(
                settings,
                arguments.packet,
                _read_decision(arguments.decision),
            )
            _emit(_json_text(receipt))
        elif arguments.command == "cycle":
            result = run_cycle(
                settings,
                allow_command_analyzer=arguments.allow_command_analyzer,
                apply=arguments.apply,
            )
            _emit(_json_text(result))
        elif arguments.command == "digest":
            digest = create_digest(settings, date=arguments.date)
            rendered = digest_markdown(digest) if arguments.format == "markdown" else _json_text(digest)
            _emit(rendered, arguments.output)
        elif arguments.command == "feedback":
            if arguments.undo:
                if arguments.source or arguments.outcome or arguments.amount is not None:
                    raise SignalDigestError("--undo cannot be combined with source/outcome/amount")
            elif not arguments.source or not arguments.outcome:
                raise SignalDigestError("feedback requires --source and --outcome, or --undo")
            event = submit_feedback(
                settings,
                source=arguments.source,
                outcome=arguments.outcome,
                amount=arguments.amount,
                undo_receipt_id=arguments.undo,
                apply=arguments.apply,
            )
            _emit(_json_text(event))
        else:  # pragma: no cover - argparse guarantees a known command.
            parser.error(f"unsupported command: {arguments.command}")
        return 0
    except (SignalDigestError, ValueError) as exc:
        print(f"signal-digest: error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
