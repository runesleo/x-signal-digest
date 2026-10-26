> Draft, not published. Public template URL: TODO. Delete this line before pasting it onto the site.

# X Signal Digest

Your own Grok reads your own X timeline once a day and keeps 0–3 posts worth knowing, each with the original link and why; if none qualify, it says so.

## The problem

You open X, scroll for twenty minutes, and close it without being able to name what you know now. Bookmarks keep growing. You do not go back the next day. Some digests still fill three slots on a day when nothing qualified.

## See it in 30 seconds

- Who reads: your own Grok, on the X home timeline you are already signed into.
- How often: once a day. Default local time is 08:00. You can change the clock time.
- What you get: at most 3 posts. Each one has the original link and why it is worth knowing.
- When nothing qualifies: it says "Nothing today."
- What it does not do: it does not like, reply, or post.

## Install

1. Open the template page and click Add to Grok Bot. The public URL stays TODO until publish.
2. Answer two questions: which 1–3 topics matter, and what to skip.
3. The first digest arrives then. After that it runs once a day at the clock time you left in place.
4. To move the clock time, tell it the new time. The cadence stays once a day.

Paste-ready instructions and schedule values live in `templates/grok-bot/` in the repo.

## Template or self-hosted

Open-source repo: [x-signal-digest](https://github.com/runesleo/x-signal-digest).

| | Grok Bot template | Self-hosted |
| --- | --- | --- |
| How you start | Add the template in Grok and name your topics | Install the repo on your own computer and bring a read-only collector |
| Where the timeline comes from | Your Grok reads X directly | Your collector writes files on your computer |
| What you get each day | 0–3 posts worth knowing | The same 0–3, plus a local receipt; at most one item can enter your own knowledge or task system |
| Where the data stays | Your Grok chat | The local state directory you choose |
| Fits | You want the timeline cut down to a few posts a day | You want the result wired into your own system, with a receipt you can check |

If a self-hosted setup reads X through a signed-in browser, the platform terms and rate-limit risk are in the repo's security notes. The Grok template does not add a collector.

## Boundaries and privacy

- The digest is a message in your Grok chat. The template forbids likes, replies, quotes, reposts, follows, bookmarks, posts, and direct messages.
- The timeline is not sent to the template author's server. The author does not receive your timeline or your login.
- An independent developer provides this template. It is not an xAI product. After you add it, the Bot runs in your own Grok account under these instructions.
- If the timeline does not load, it says "Timeline unread. This round does not count." That round must not be reported as "Nothing today."
- Post text is content. The Bot does not follow instructions inside a post that tell it to repost, message someone, or change these rules.
- You can change topics and clock time later. Turn the schedule off and the daily send stops.
