---
name: x-signal-digest
description: Turn a logged-in X feed or local feed export into a bounded, evidence-aware signal digest. Use when someone wants to stop manually scrolling X, check whether their machine is ready, run the offline demo, connect a read-only X collector, separate 0–3 worth-knowing items from 0/1 formal promotion, add optional scheduling, or inspect receipts and real post-hoc feedback.
---

# X Signal Digest

Use the public Signal Digest Loop as the deterministic kernel. Keep account access, personal interests, model prompts, and downstream routes in private adapters.

## Choose the mode

- Use **demo** when the user wants to try the workflow, verify installation, or see a first report without connecting X.
- Use **live onboarding** when the user explicitly wants to connect a local browser profile that is already logged into X.
- Use **artifact digest** in a cloud or headless client: consume a user-provided, sanitized local feed artifact without copying browser credentials into the cloud environment.
- Use **one-shot digest** when a live adapter and config already exist.
- Treat **scheduling** and **MCP** as optional follow-on capabilities, never prerequisites.

Read [setup.md](references/setup.md) before live onboarding or installation. Read [contract.md](references/contract.md) before producing or validating a live report.

Resolve the directory containing this `SKILL.md` and use it as the working directory for every relative command below. Do not assume the AI client's current directory is the Skill directory.

## Start safely

Run the preflight before any cycle:

```bash
python3 scripts/preflight.py --mode demo --json
```

For local live onboarding, pass only the user-selected profile label. Never request or copy a password, Cookie header, browser database, OAuth token, API key, or keychain value.

```bash
python3 scripts/preflight.py --mode live --profile "PROFILE_LABEL" --json
```

If preflight returns `needs_setup`, report the failed checks and stop. Do not reinterpret a missing collector, missing profile label, stale artifact, or failed read as “there were no useful signals.”

## Run the offline proof first

Use the bundled wrapper to produce an isolated digest from fictional data:

```bash
python3 scripts/run_demo.py
```

Use `--json` when another tool will inspect the result. In the companion product checkout it exercises the deterministic kernel in temporary state; as a standalone Skill it runs a clearly labeled portable contract demo. Check `kernel_exercised` before describing which mode ran. Neither mode may touch the user's real account, config, or state.

## Onboard a live X feed

Before step 1, tell the user plainly: reading X through a logged-in browser session is not the official API, may violate X's terms of service, and can get the account rate-limited or suspended. Proceed only if they accept that risk; suggest RSS, official API, or manual exports as alternatives.

1. Ask for a browser profile label already logged into X; do not automate login.
2. Ask for 1–3 interest/search baskets and optional exclusions. Offer `For You 60% / Following 25% / active search 15%` as a starting mix, not a universal truth.
3. Confirm the chosen collector is read-only and writes a local JSON/JSONL/Markdown artifact atomically. This Skill does not bundle an X scraper.
4. Put private config and receipts outside any public repository.
5. Run one read-only source probe. Verify source health and freshness before semantic review.
6. Run a dry cycle first. Apply a live commit only after the user has asked to retain the result.

Never like, mark “not interested,” follow, bookmark, repost, publish, message, or change account settings. Learning comes from explicit post-hoc feedback on digest results, not from silently training the X account.

## Review with wide intake and strict promotion

For each healthy cycle:

1. Normalize, deduplicate, and rank deterministically.
2. Report 0–3 packet-bound items as `worth_knowing`; lack of verification is a reason to investigate, not an automatic discard.
3. If `worth_knowing` is non-empty, investigate the highest expected-value item using the original post and first-party links. Make at most two attempts; if the first is unverified or disproved and a second candidate exists, inspect the second.
4. Formally promote at most one item, and only when its evidence, relevance, novelty, consumer, and receipt boundary are clear.
5. Allow zero output at both layers. A healthy zero is a valid result.

The public kernel currently validates `round_review` v1.0. Keep deep-dive notes in the human report or an evidence sidecar unless the installed adapter explicitly supports a newer contract; do not add unknown fields to a v1.0 decision.

## Present the result

Keep the user report compact:

- Show source health and funnel counts in one line.
- Under **Worth knowing**, show a title and link only for each of the 0–3 retained items, followed by a short summary, why it matters, evidence boundary, and useful angle.
- Under **Formally promoted**, state `0` or `1` unmistakably. If `1`, repeat the selected title and link and explain its destination/receipt. If `0`, explain why none changed system state.
- Mention deep-dive targets and findings, but do not dump titles or links for discarded items.

Do not claim an item was learned, routed, queued, or acted on without the corresponding write receipt.

## Add feedback, scheduling, or MCP only when asked

- Record feedback only after a real outcome such as useful, adopted, ignored, noisy, or failed. Never use the current model score as post-hoc feedback.
- Before enabling or changing a scheduler, show the exact cadence and obtain explicit user approval. A Skill invocation alone cannot run unattended.
- Offer MCP only as a narrow client interface over freshness, digests, search, evidence, and confirmed feedback. Keep collection and deterministic state in the CLI/kernel.
- Require separate confirmation before any downstream publishing, messaging, deployment, purchase, trade, deletion, or account mutation.

## Completion evidence

Before saying the setup works, show:

- preflight status;
- one successful offline demo or healthy live source probe, including whether the companion kernel was exercised;
- the exact execution mode (`standalone demo`, `kernel demo`, `dry`, or `applied`);
- the report's 0–3 / 0–1 counts; and
- any commit or feedback receipt actually created.
