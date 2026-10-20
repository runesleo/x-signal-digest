#!/usr/bin/env python3
"""Check portable prerequisites without reading credentials or account data."""

from __future__ import annotations

import argparse
import json
import platform
import shutil
import sys
from pathlib import Path
from typing import Any


PRODUCT_ROOT = Path(__file__).resolve().parents[3]


def _adjacent_kernel_available() -> bool:
    required_files = [
        PRODUCT_ROOT / "demo.py",
        PRODUCT_ROOT / "pyproject.toml",
        PRODUCT_ROOT / "src" / "signal_digest_loop" / "__init__.py",
    ]
    return all(path.is_file() for path in required_files)


def _check(name: str, ok: bool, detail: str, *, required: bool = True) -> dict[str, Any]:
    return {
        "name": name,
        "status": "pass" if ok else ("fail" if required else "optional_missing"),
        "required": required,
        "detail": detail,
    }


def build_report(mode: str, profile: str | None, collector: str, search: str) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    python_ok = sys.version_info >= (3, 11)
    checks.append(
        _check(
            "python",
            python_ok,
            f"{platform.python_implementation()} {platform.python_version()} (requires >=3.11)",
        )
    )

    profile_label = (profile or "").strip()
    collector_path = shutil.which(collector)
    search_path = shutil.which(search) if search else None
    adjacent_kernel = _adjacent_kernel_available()
    installed_kernel = shutil.which("signal-digest") is not None
    if mode == "demo":
        checks.append(
            _check(
                "portable_demo",
                True,
                "bundled fictional contract demo available",
            )
        )
    if mode == "live":
        checks.append(
            _check(
                "signal_digest_kernel",
                adjacent_kernel or installed_kernel,
                (
                    "adjacent public kernel checkout detected"
                    if adjacent_kernel
                    else (
                        "installed signal-digest command detected"
                        if installed_kernel
                        else "companion Signal Digest Loop CLI not found"
                    )
                ),
            )
        )
        checks.append(
            _check(
                "browser_profile_declared",
                bool(profile_label),
                (
                    "profile label supplied"
                    if profile_label
                    else "pass --profile with a local profile label already logged into X"
                ),
            )
        )
        checks.append(
            _check(
                "read_only_collector",
                collector_path is not None,
                (
                    f"command available: {Path(collector).name}"
                    if collector_path
                    else f"command not found: {Path(collector).name}"
                ),
            )
        )
        if search:
            checks.append(
                _check(
                    "active_search_helper",
                    search_path is not None,
                    (
                        f"command available: {Path(search).name}"
                        if search_path
                        else f"optional command not found: {Path(search).name}"
                    ),
                    required=False,
                )
            )

    failed = [row["name"] for row in checks if row["status"] == "fail"]
    return {
        "schema_version": "x-signal-digest-preflight-1.0",
        "mode": mode,
        "status": "ready" if not failed else "needs_setup",
        "failed_checks": failed,
        "checks": checks,
        "account_boundary": {
            "profile_declared": bool(profile_label),
            "login_state": "unchecked",
            "credentials_read": False,
            "account_mutations_allowed": False,
            "next_live_check": (
                "Run a single read-only feed probe with the selected collector; do not infer login from this preflight."
                if mode == "live" and not failed
                else None
            ),
        },
    }


def render(report: dict[str, Any]) -> str:
    lines = [f"X Signal Digest preflight: {report['status']} ({report['mode']})"]
    for row in report["checks"]:
        lines.append(f"- {row['name']}: {row['status']} — {row['detail']}")
    if report["account_boundary"]["next_live_check"]:
        lines.append(f"- next: {report['account_boundary']['next_live_check']}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("demo", "live"), default="demo")
    parser.add_argument("--profile", help="local browser profile label; never a cookie or password")
    parser.add_argument("--collector-command", default="xreach")
    parser.add_argument(
        "--search-command", default="", help="optional active-search helper to check; skipped when empty"
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    report = build_report(args.mode, args.profile, args.collector_command, args.search_command)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        sys.stdout.write(render(report))
    return 0 if report["status"] == "ready" else 2


if __name__ == "__main__":
    raise SystemExit(main())
