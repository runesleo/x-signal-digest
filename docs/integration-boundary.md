# Public kernel and private adapters

Signal Digest Loop is designed to be embedded without absorbing the private
system around it.

## Public kernel

The reusable package owns:

- JSON, JSONL, and Markdown artifact reading;
- configurable field mapping;
- per-source freshness and health;
- canonical identity, deduplication, processed-item TTL, and deterministic
  ranking;
- bounded shortlist packets;
- the command analyzer protocol and 0/1 validation;
- local commit state, receipts, digest generation, and reversible feedback.

It can be tested entirely with synthetic files.

## Private input adapters

A collector may use an authenticated API, an RSS client, an email export, a
database query, or a browser. Its only contract with the kernel is to write a
configured artifact safely. Prefer an atomic temporary-file rename so a cycle
never reads a half-written feed.

Keep source identifiers, credentials, proxies, cookies, account handles, and
terms-of-service logic in that adapter's private environment.

## Private analyzer adapters

The analyzer may be the included deterministic rules example, a local model,
or a remote-model client. It owns relevance to the operator's actual goals. It
must still return the same packet-bound 0/1 decision JSON.

Keep proprietary prompts, goal context, identity data, and model credentials
outside the public configuration. If necessary, have the analyzer load them
from its own protected store rather than placing them in the packet.

## Private output adapters

The public commit receipt is the integration seam. A consumer can map opaque
disposition `route` values such as `maintenance_review` or `editorial_review`,
together with disposition types such as `learn` or `act`, to its own knowledge
store, task tracker, or drafting queue. `relation.targets` separately records
which goals, assets, or decisions the signal affects.

Route labels do not grant authority. An adapter that publishes, sends a
message, deploys code, spends money, or changes an account should implement an
explicit approval and idempotency boundary of its own.

## Upgrade rule

Depend on documented packet and receipt fields, tolerate additive fields, and
pin the package version. Do not make private consumers depend on incidental
filenames, console prose, or internal Python functions.
