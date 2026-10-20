# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses
[Semantic Versioning](https://semver.org/).

## [0.1.0] - 2026-10-20

### Added

- Offline-first kernel: JSON / JSONL / Markdown intake, source health, deduplication, ranking, processed TTL.
- 0–3 round review and a strict 0-or-1 promotion contract with packet-bound, idempotent receipts.
- Receipt-only digest and bounded, reversible source-weight feedback.
- `x-signal-digest` Agent Skill with offline demo and read-only preflight.
- `examples/adapters/xreach_to_jsonl.py`: offline converter from an xreach JSON export to kernel rows.
- Disabled scheduling examples for cron, launchd and GitHub Actions.

### Known issues

- Two different decisions for the same packet can both commit (identical decisions are idempotent).
- The demo rule-based analyzer can pick an action item outside its top three, which the kernel rejects.

### Security

- Documented the platform and terms-of-service risk of browser-session X collectors.
