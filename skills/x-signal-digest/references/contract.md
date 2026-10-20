# Digest and evidence contract

## Stable layers

1. **Collector adapter**: private and read-only; writes an atomic local artifact.
2. **Deterministic kernel**: checks freshness/health, normalizes, deduplicates, ranks, bounds the shortlist, commits receipts, builds digests, and stores reversible feedback.
3. **Semantic analyzer**: model-neutral; returns packet-bound judgments.
4. **Optional consumers**: map receipt routes into private knowledge, task, or content systems with their own approval gates.
5. **Optional MCP**: exposes narrow read/query/confirmed-feedback tools over existing artifacts.

Do not merge these layers into an all-powerful Agent.

## Health before semantics

A cycle is eligible for review only when required sources are present, parseable, fresh, and above the configured coverage floor. Infrastructure failure and source failure are distinct from a healthy zero-result cycle.

Never reuse an old successful artifact as if it were the latest failed run. Preserve run identity and timestamps in receipts.

## Wide intake, strict promotion

- `worth_knowing`: 0–3 exact shortlist candidates. Each needs a short summary, importance, evidence status/boundary, and a useful angle.
- evidence follow-up: 0 attempts only when `worth_knowing` is empty; otherwise inspect the best candidate, then at most one fallback candidate.
- formal promotion: 0 or 1 candidate. It must also appear in `worth_knowing` and have enough verified or mixed evidence for the claims and route being asserted.
- discard: everything else, summarized by reason; no titles or links are needed in the human report.

Evidence follow-up should prioritize the exact original post and first-party sources such as official documentation, repositories, company disclosures, or original research. Separate fact, attributed self-report, opinion, forecast, marketing, and inference.

The public kernel's current exact decision contract is `round_review` v1.0 and rejects unknown fields. Keep follow-up details in a report/evidence sidecar unless the installed adapter explicitly implements a newer schema.

## Human report

Use this order:

```text
Source: healthy 5/5 · raw 80 · shortlist 12

Worth knowing (0–3)
1. Title — source link
   Summary: ...
   Why: ...
   Evidence: verified / attributed / mixed / insufficient; boundary ...
   Use: ...

Formally promoted (0/1)
- #1 Title — source link
  Destination/receipt: ...

Deep dive: #1 verified; #2 not attempted
Discarded: 9 · main reasons ...
```

Only worth-knowing, deep-dive, and promoted items need titles or links. Label the promoted item unmistakably; do not make the user infer it from the list.

## State and feedback

- Dry cycle: may prepare and analyze; does not commit processed state.
- Applied cycle: validates and commits one immutable receipt plus local processed state.
- Feedback: must come from a later real outcome. It may adjust bounded source weights and must be reversible.
- Current model scores or same-round judgments are not post-hoc feedback.
- X likes, “not interested,” follows, bookmarks, reposts, and posts are account mutations and are outside this Skill's default boundary.

## Authority boundaries

The kernel may record opaque route labels, but labels grant no authority. Require separate explicit confirmation and idempotency for publishing, messaging, deployment, payment, trading, deletion, credential handling, or scheduler changes.

