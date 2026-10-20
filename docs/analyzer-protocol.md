# Command analyzer protocol

Signal Digest Loop delegates qualitative judgment to a command. This protocol
keeps that command model-agnostic and makes its decision auditable.

Every decision has two separate layers: `round_review` reports zero to three
shortlist items worth knowing, while top-level `selection` promotes zero or one
of those items into the strict evidence and disposition contract. The review
layer is audit/report data only; it grants no action authority and does not
relax null-selection rules.

## Transport

The configured command is executed directly, without a shell. It receives one
UTF-8 JSON object on standard input and must write one UTF-8 JSON object to
standard output. Diagnostic logs belong on standard error. Extra text on
standard output makes the response invalid.

The command must be a TOML argument array, not a shell string. The kernel uses a
minimal environment and enforces `analyzer.timeout_seconds`, a 1 MiB stdout
limit, a zero exit status, JSON syntax, and schema constraints. The command is
trusted local code; the kernel does not sandbox it.

## Input packet

The packet contains a stable `packet_id`, source-health evidence, and a bounded
`shortlist`. A representative packet is:

```json
{
  "schema_version": "1.0",
  "packet_id": "pkt_example_001",
  "created_at": "2026-01-15T10:00:00Z",
  "policy": {
    "promotion_limit": 1,
    "promotion_threshold": 0.55,
    "shortlist_limit": 5,
    "stale_sources_eligible": false
  },
  "source_health": [
    {
      "name": "fictional-lab-feed",
      "status": "healthy",
      "items_seen": 3,
      "age_hours": 0.2,
      "errors": []
    }
  ],
  "shortlist": [
    {
      "id": "sig_example_001",
      "source": "fictional-lab-feed",
      "title": "Fictional cache policy changes next week",
      "url": "https://example.invalid/notes/cache-change",
      "text": "A made-up service announces a configuration migration.",
      "score": 0.82
    }
  ]
}
```

Fields may be added in later compatible releases. An analyzer should ignore
unknown fields, but it must never invent candidate identifiers.

## Output: select zero

Zero is a complete and expected result:

```json
{
  "schema_version": "1.0",
  "packet_id": "pkt_example_001",
  "selection": null,
  "no_signal_reason": "No item changes a current decision.",
  "claims": [],
  "relation": {"summary": "", "targets": []},
  "memory_check": {"status": "not_checked", "notes": ""},
  "knowledge_delta": {"summary": "", "novelty": "none"},
  "dispositions": [],
  "timeliness": {"status": "expired", "expires_at": null},
  "effort": {"level": "none", "estimate": ""},
  "gates": [],
  "round_review": {
    "schema_version": "1.0",
    "worth_knowing": [
      {
        "candidate_id": "sig_example_001",
        "title": "Fictional cache policy changes next week",
        "source_ref": "https://example.invalid/notes/cache-change",
        "why_it_matters": "It may inform a later maintenance review.",
        "evidence_status": "attributed_unverified",
        "evidence_boundary": "Only the fictional source artifact was inspected.",
        "utilization_angles": [
          {
            "angle": "workflow",
            "fit": "later",
            "suggestion": "Retain the readiness check for a future review."
          }
        ]
      }
    ],
    "formal_selection": {
      "count": 0,
      "selected_id": null,
      "summary": "No item changes a current decision."
    },
    "discard_summary": {"count": 0, "reasons": []}
  }
}
```

`no_signal_reason` must be specific enough to distinguish deliberate abstention
from analyzer failure. The rest of a zero decision is strictly inert:
`claims`, `dispositions`, and `relation.targets` are empty;
`knowledge_delta.novelty` is `none`; timeliness is `expired` with a null expiry;
and effort is `none`. Any hidden claim, route, target, novelty, future
timeliness, or effort makes the decision invalid.

The example still reports one packet item as worth knowing. With a null
selection, `round_review.formal_selection.summary` must exactly equal the
top-level `no_signal_reason`.

## Output: select one

To promote a candidate, return its exact `id` plus the full evidence and
decision contract:

```json
{
  "schema_version": "1.0",
  "packet_id": "pkt_example_001",
  "selection": "sig_example_001",
  "claims": [
    {
      "statement": "The fictional note describes a configuration migration.",
      "evidence": ["https://example.invalid/notes/cache-change"]
    }
  ],
  "relation": {
    "summary": "The migration is relevant to maintenance readiness.",
    "targets": ["maintenance_review"]
  },
  "memory_check": {
    "status": "not_checked",
    "notes": "The public demo has no private memory adapter."
  },
  "knowledge_delta": {
    "summary": "A new readiness check is available.",
    "novelty": "medium"
  },
  "dispositions": [
    {
      "type": "act",
      "route": "maintenance_review",
      "rationale": "The change is time-bounded and the check is reversible.",
      "next_action": "Review the fictional cache configuration."
    }
  ],
  "timeliness": {"status": "soon", "expires_at": null},
  "effort": {"level": "low", "estimate": "15 minutes"},
  "gates": [
    {
      "name": "external_action",
      "status": "not_applicable",
      "notes": "Synthetic demo only."
    }
  ],
  "round_review": {
    "schema_version": "1.0",
    "worth_knowing": [
      {
        "candidate_id": "sig_example_001",
        "title": "Fictional cache policy changes next week",
        "source_ref": "https://example.invalid/notes/cache-change",
        "why_it_matters": "It may change a reversible maintenance decision.",
        "evidence_status": "attributed_unverified",
        "evidence_boundary": "Only the fictional source artifact was inspected.",
        "utilization_angles": [
          {
            "angle": "workflow",
            "fit": "now",
            "suggestion": "Review the fictional cache configuration."
          }
        ]
      }
    ],
    "formal_selection": {
      "count": 1,
      "selected_id": "sig_example_001",
      "summary": "One maintenance item clears the formal decision gate."
    },
    "discard_summary": {"count": 0, "reasons": []}
  }
}
```

The disposition vocabulary is intentionally small: `discard`, `observe`,
`learn`, `act`, or `content`. Every disposition has a non-empty, opaque `route`;
the public kernel records it but does not know how to deliver it. A private
receipt consumer owns that mapping. `discard` must be the only disposition when
used. A non-null `timeliness.expires_at` must be a timezone-aware ISO-8601
timestamp.

## `round_review` v1 contract

`round_review` is required in every analyzer decision and is copied unchanged
to the top level of a commit receipt. Its objects reject missing and unknown
fields.

Receipt-derived JSON digests retain the existing formal `entries` and counters,
and additionally expose `round_review_count`, `worth_knowing_count`, and
`worth_knowing_entries`. Each awareness entry carries its `receipt_id`,
`packet_id`, commit time, candidate identity and exact review fields, plus a
`formal_selected` boolean. Consequently, an awareness-bearing receipt remains
in the digest even when its formal selection is null.

`worth_knowing` contains zero to three entries drawn from the packet shortlist.
Candidate IDs must be unique. Each entry has exactly:

- `candidate_id`: an exact shortlist ID;
- `title`: the candidate's exact packet title;
- `source_ref`: the candidate's exact non-empty `url`, or its exact `source`
  when no URL is present;
- non-empty `why_it_matters` and `evidence_boundary` strings;
- `evidence_status`: `verified`, `attributed_unverified`, `mixed`, or
  `insufficient`; and
- one or more unique `utilization_angles`. Each angle has exactly `angle`,
  `fit`, and a non-empty `suggestion`. `angle` is one of `business`, `product`,
  `strategy`, `research`, `content`, `workflow`, or `learning`; `fit` is `now`,
  `later`, or `not_suitable`.

`formal_selection` has exactly `count`, `selected_id`, and a non-empty
`summary`. Count is `0` or `1` and both count and selected ID must match the
top-level selection. A selected ID must also occur in `worth_knowing`. With a
null selection, the summary must exactly match `no_signal_reason`.

`discard_summary` has exactly a non-negative `count` and a `reasons` array of
non-empty strings. The count must reconcile the full packet shortlist:

```text
packet shortlist count = unique worth-knowing count + discard count
```

Reasons must be empty when discard count is zero and non-empty otherwise. They
may summarize categories rather than repeat one reason per discarded item.

## Fail-closed rules

A decision is rejected when any of these conditions holds:

- the packet ID differs from the packet being committed;
- more than one item is selected;
- the selected candidate is absent from the packet shortlist;
- the selected candidate's score is below the packet promotion threshold;
- `round_review` is absent, contains unknown fields, refers to an unknown or
  duplicate candidate, changes a title/source reference, exceeds three items,
  uses an unsupported enum, or does not reconcile the shortlist;
- formal-selection count or ID differs from the top-level selection;
- a zero decision omits its reason;
- a selected decision omits claims, relation, knowledge delta, dispositions,
  timeliness, effort, or gates;
- a disposition omits its route, or combines `discard` with another
  disposition;
- standard output is not exactly one JSON object; or
- the command times out or exits nonzero.

Rejection does not silently become a zero decision. It is an execution error,
which keeps analyzer outages distinct from genuine no-signal cycles.

## Security guidance

Shortlist text is untrusted data. Treat it as capable of containing prompt
injection, terminal escapes, markup, or misleading instructions. Analyzer code
should use structured serialization, avoid a shell, restrict any tools exposed
to a model, cap input/output size, and keep credentials outside emitted JSON.

The deterministic example in
[`../examples/rule_based_analyzer.py`](../examples/rule_based_analyzer.py) uses
the standard library and no external service.
