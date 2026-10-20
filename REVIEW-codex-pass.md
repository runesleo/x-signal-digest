# Independent review — v0.1.0 (Codex pass)

An independent Codex review was run read-only against the release candidate on 2026-10-20, with the instruction to evaluate from scratch rather than reuse the author's framing. Findings and their disposition:

## 🔴 Blockers (all fixed before first push)

| Finding | Fix |
| --- | --- |
| The privacy regression test listed instance-specific strings (split with `+`), which itself disclosed them. | The public test now checks only generic home-directory paths; instance-specific strings live in a local file referenced by `SIGNAL_DIGEST_PRIVATE_DENYLIST`, outside the repository. The public history starts from a single clean commit. |
| `install.md` mixed relative paths and did not show where the CLI lands; a copied Skill could not find the kernel while the demo check still passed. | Every command now uses full paths under `$HOME/x-signal-digest`; the Skill is symlinked, and first success requires `"kernel_exercised": true`. Verified in a clean temporary `HOME` (clone → venv → install → demo, ~8 s). |

## 🟡 Warnings

| Finding | Disposition |
| --- | --- |
| Huge numbers or extreme dates could raise `OverflowError` and abort a cycle. | Fixed: treated as an invalid row / unparseable date. |
| xreach adapter turned an error payload into an empty "healthy" source and could overwrite the last good file. | Fixed: non-export payloads exit 2; `--output` replaces atomically. Test added. |
| Source-health errors and preflight could echo absolute paths. | Fixed for OS errors and preflight command names; remaining edge cases listed under Known limitations. |
| Chinese headline implied built-in automatic collection. | Fixed: states that collection comes from your own collector. |
| README claimed `demo.py` reports `kernel_exercised`. | Fixed: attributed to the Skill wrapper. |
| Two different decisions for the same packet can both commit. | Documented as a known issue for v0.1. |
| Demo analyzer can pick an action item outside its top three. | Documented as a known issue; demo-only analyzer. |

## 🟢 Confirmed OK

- Tests and the offline demo pass.
- Analyzer runs with argument arrays, `shell=False`, explicit opt-in; no path from source text to a shell.
- Platform / terms-of-service risk of browser-session collectors is disclosed consistently in English and Chinese.
- No credentials or private feed content found; fixtures are fictional.
