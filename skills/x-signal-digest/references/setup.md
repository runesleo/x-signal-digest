# Setup and client boundary

## Install the Skill

Keep this directory intact as `x-signal-digest`. Agent clients that implement the open Agent Skills format can discover it from the Agent Skills directory documented by that client.

A symlink to one canonical checkout is preferable to three copied, drifting versions when the client follows symlinks.

## First proof: no X account

From the Skill directory:

```bash
python3 scripts/preflight.py --mode demo --json
python3 scripts/run_demo.py
```

The demo requires no account, key, network, scheduler, MCP server, or package installation. In the companion product checkout it exercises the deterministic kernel in temporary state. If the Skill is installed alone, it runs a clearly labeled portable contract demo and reports `kernel_exercised=false`.

## Live X prerequisites

The Skill deliberately does not bundle login automation, a live X collector, or the full deterministic kernel. A live setup needs:

1. a local browser profile the user has already logged into X;
2. the companion Signal Digest Loop CLI, either installed or available in the product checkout;
3. a user-selected, read-only collector available on `PATH` (the preflight default is `xreach`);
4. an atomically written local JSON, JSONL, or Markdown artifact;
5. a private config and state directory outside any public checkout; and
6. a one-shot read-only probe that proves the profile and source are actually usable.


**Platform risk.** Browser-session collectors are not the official X API and may violate X's terms of service; the account can be rate-limited, challenged, or suspended. Tell the user this before live onboarding, keep collection read-only and low-frequency, and stop on any verification or rate-limit prompt. For xreach exports, `examples/adapters/xreach_to_jsonl.py` in the product checkout converts the file offline.

Pass only a profile label to preflight:

```bash
python3 scripts/preflight.py --mode live --profile "PROFILE_LABEL" --json
```

Preflight never opens browser databases and never reads cookies, passwords, tokens, keychains, or account data. It does not print the profile label or any filesystem path. It reports login state as `unchecked`; the later source probe is the evidence.

## Local versus cloud clients

A local AI client can invoke a local read-only collector against a browser profile the user has already logged into. A cloud or headless client cannot see that desktop login state. In cloud mode, provide a sanitized feed artifact or run only the demo/kernel; never upload a browser profile, cookie store, keychain, or session token to make local collection appear portable.

The Skill contract is portable across compatible clients. Browser access, collectors, local files, MCP servers, and schedulers remain host capabilities and must be configured separately in each environment.

Suggested starting mix:

- For You: 60%
- Following: 25%
- 1–3 explicit search baskets in total: 15%

This is a starting configuration, not a promise of universal relevance. Tune it from real digest outcomes.

## What a Skill can and cannot do

The Skill makes the workflow portable across compatible AI clients. The deterministic CLI/kernel keeps health, deduplication, ranking, receipts, digest, and feedback consistent.

A Skill invocation does not wake itself up. For unattended runs, the user must explicitly approve and install a scheduler in the host environment. Keep scheduling optional and show the exact cadence before changing it.

MCP is also optional. It is useful as a narrow interface for reading freshness, digests, search results, evidence, and confirmed feedback. It should not own X login, cookies, collection, ranking state, or publishing.

## Private data checklist

Never place these in the Skill or public repository:

- browser profile paths or copied browser databases;
- cookies, passwords, OAuth tokens, API keys, proxies, or account handles;
- private interests, exclusions, goals, tasks, memory, or content routes;
- source excerpts or receipts that reveal private browsing context; or
- scheduler definitions containing machine-specific secrets or paths.
