# Security and privacy

Signal Digest Loop is deliberately local and narrow, but local processing is
not automatically safe processing. This document defines the public core's
boundary and the operator responsibilities around it.

## Default boundary

The kernel reads configured files, invokes one configured analyzer command,
and writes state and receipts. It does not:

- discover or use credentials;
- log in to sources;
- call remote APIs;
- install or enable a scheduler;
- publish, message, deploy, purchase, trade, or delete;
- execute route labels; or
- upload telemetry.

`cycle` is dry-safe by default. State-changing commit behavior requires
`--apply`.

## Resource limits

Local files are untrusted inputs, so the kernel applies finite limits before
they can reach ranking or the analyzer:

| Setting | Default | Accepted range | Scope |
| --- | ---: | ---: | --- |
| `max_source_bytes` | 10,485,760 | 1,024–1,073,741,824 | Each source artifact |
| `max_rows` | 5,000 | 1–1,000,000 | Global budget shared across all sources in a cycle |
| `max_line_bytes` | 262,144 | 128–16,777,216 | Each JSONL line |
| `max_errors` | 50 | 1–100,000 | Parse or invalid-row tolerance |
| `max_engagement_depth` | 4 | 1–32 | Nested engagement aggregation |

These defaults apply even when `[limits]` is omitted. If a source exceeds a
limit, its health becomes `invalid` and it contributes no shortlist candidates.
The global row budget is consumed in configured source order; once exhausted,
remaining sources are invalid for that cycle rather than being silently
sampled.

The accepted ranges prevent accidental nonsensical configuration; they are not
a promise that every value inside the range is safe for every machine. Raising
limits expands memory, CPU, disk, analyzer-input, and denial-of-service
exposure. Lowering them can reject legitimate artifacts. Change one limit at a
time, test with synthetic boundary cases, inspect source-health evidence, and
size the process at the operating-system or container layer as well.

## Trust zones

1. **Source artifacts are untrusted.** They can contain malformed JSON,
   misleading claims, prompt injection, dangerous links, or very large fields.
2. **Configuration is trusted operator input.** It chooses readable files and
   the executable analyzer command.
3. **The analyzer command is trusted executable code.** It runs with the
   invoking user's OS permissions and is not sandboxed by this package.
4. **Receipts are sensitive output.** They may preserve source excerpts,
   URLs, decisions, and rationales.
5. **Route adapters are outside the kernel.** Their permissions and approval
   gates must be reviewed independently.

A `selection: null` decision is also fail-closed and strictly inert: `claims`,
`dispositions`, and `relation.targets` must be empty; knowledge novelty must be
`none`; timeliness must be `expired` with a null expiry; and effort must be
`none`. A non-empty no-signal reason remains required for auditability.

## Recommended controls

- Run under a dedicated, least-privileged account or container when processing
  hostile feeds.
- Give source collectors write access only to their artifact directory; give
  the digest loop read access there and write access only to `state_dir`.
- Configure analyzer commands as argument arrays. Never concatenate source text
  into a shell command.
- If an analyzer calls a hosted model, minimize data, redact secrets, document
  retention, and keep API keys in the adapter's secret store—not in TOML,
  packets, decisions, or receipts.
- Put state outside public repositories. Encrypt it at rest when URLs or
  excerpts are confidential.
- Apply size and retention limits appropriate to the source. Delete receipts
  according to policy only after downstream consumers no longer need them.
- Require a separate approval gate before a route consumer performs an
  irreversible or external action.
- Review optional scheduler definitions before installation and prevent
  overlapping runs with the platform's supported locking mechanism.

## Reporting a vulnerability

Do not include production data, credentials, or exploit traffic in a public
issue. Share the smallest synthetic reproduction that demonstrates the flaw and
follow the repository's security-reporting channel when one is published.
