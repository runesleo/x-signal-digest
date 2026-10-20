#!/usr/bin/env python3
"""Convert an xreach timeline/search/list JSON export into kernel JSONL rows.

Read-only and offline: this script only reshapes a file you already exported.
It never calls X, never reads cookies, and keeps no account identifiers beyond
the public author handle needed to build the post URL.

    xreach home -n 100 --json > feed.json        # your own collector run
    python3 xreach_to_jsonl.py feed.json --output signals.jsonl

A payload that is not a list or an object with an ``items`` list (for example
an error or rate-limit response) exits with status 2 and leaves the previous
output file untouched. With ``--output`` the file is replaced atomically.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any

ENGAGEMENT_KEYS = ("likeCount", "retweetCount", "replyCount", "quoteCount", "bookmarkCount")


def _published(raw: Any) -> str | None:
    if not isinstance(raw, str) or not raw:
        return None
    try:
        parsed = parsedate_to_datetime(raw)  # X's "Wed Oct 10 20:19:24 +0000 2018"
    except (TypeError, ValueError):
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


class ExportShapeError(ValueError):
    """The input is not an xreach item export (e.g. an error response)."""


def convert(payload: Any, *, include_retweets: bool = False) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        items = payload
    elif isinstance(payload, dict) and isinstance(payload.get("items"), list):
        items = payload["items"]
    else:
        keys = sorted(payload)[:5] if isinstance(payload, dict) else type(payload).__name__
        raise ExportShapeError(f"not an xreach item export (got {keys})")
    rows: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict) or not item.get("id"):
            continue
        if item.get("isRetweet") and not include_retweets:
            continue
        user = item.get("user") if isinstance(item.get("user"), dict) else {}
        handle = str(user.get("screenName") or "i")
        text = str(item.get("text") or "").strip()
        rows.append(
            {
                "title": f"@{handle}: {text.splitlines()[0][:120]}" if text else f"@{handle}",
                "url": f"https://x.com/{handle}/status/{item['id']}",
                "text": text,
                "published_at": _published(item.get("createdAt")),
                "engagement": {key: item.get(key, 0) for key in ENGAGEMENT_KEYS},
            }
        )
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("path", help="xreach JSON export, or - for stdin")
    parser.add_argument("--include-retweets", action="store_true")
    parser.add_argument("--output", help="write JSONL here atomically instead of stdout")
    args = parser.parse_args(argv)
    try:
        if args.path == "-":
            payload = json.load(sys.stdin)
        else:
            with open(args.path, encoding="utf-8") as handle:
                payload = json.load(handle)
        rows = convert(payload, include_retweets=args.include_retweets)
    except (json.JSONDecodeError, ExportShapeError) as exc:
        sys.stderr.write(f"xreach_to_jsonl: {exc}\n")
        return 2
    text = "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows)
    if not args.output:
        sys.stdout.write(text)
        return 0
    target = os.path.abspath(args.output)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(target), prefix=".xreach-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.replace(tmp, target)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
