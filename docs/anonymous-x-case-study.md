# Anonymous case study: 80 signals, one durable result

This is an aggregate, redacted account of one real personalized-feed cycle.
No account handles, post text, private interests, credentials, or internal task
names are included.

## The funnel

```text
142 source appearances
  ↓ deduplicate
80 unique items
  ↓ deterministic relevance and quality gates
23 eligible items
  ↓ bounded semantic review
12-item shortlist
  ↓ evidence, memory-difference, and usefulness review
3 worth knowing
  ↓ durable writeback contract
1 formal promotion
```

The other two worth-knowing items were still visible in the human review, but
they did not become formal decisions. One was an interesting hypothesis without
enough primary evidence. The other was a product rumor. The promoted item had a
primary project source, added knowledge that was not already present, and
returned a verifiable writeback receipt.

That distinction is the point of the loop:

- **worth knowing** controls human awareness;
- **formal promotion** controls durable state and downstream routing;
- zero formal promotions remains a valid outcome.

## What this run taught us

The strict final gate behaved correctly, but the upstream ranker still needed
work. A first-party product announcement and two directly relevant workflow
examples scored below less useful promotional posts. The next ranking revision
therefore needs to reward primary-source evidence and direct workflow fit before
using engagement as a tie-breaker.

## Public proof, private data

The aggregate funnel, decision boundaries, and receipt semantics are safe to
share. A personalized feed is not. A public demo should use fictional fixtures
or aggregate counts like these; authenticated collectors, account state,
personal memory, and private routing stay in local adapters.
