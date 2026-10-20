# Optional automation

Signal Digest Loop has no daemon and never installs a schedule. Automation is
an operator-owned wrapper around this command:

```bash
signal-digest cycle --config /path/to/config.toml --allow-command-analyzer --apply
```

The files under [`../examples/automation`](../examples/automation) are disabled
templates. They are not installed, loaded, or registered by the package.

## Before enabling a schedule

- Run a dry cycle and an applied cycle manually.
- Inspect packet, decision, and commit receipts.
- Use explicit absolute paths in the installed scheduler definition; schedulers
  often have a smaller environment than an interactive shell.
- Keep private configuration and state outside a public checkout.
- Prevent overlapping runs and set a bounded command timeout.
- Decide how failures become visible without treating a valid zero-result cycle
  as an incident.
- Rotate or prune receipts according to a written retention policy.
- Keep route consumers separately gated.
- Treat `--allow-command-analyzer` as executable-code authorization: use it only
  after reviewing the exact configured command and its environment.

## cron

[`cron.example`](../examples/automation/cron.example) is a commented crontab
line. Replace placeholders, review it with `crontab -l`, and only then install a
line explicitly. The package does not invoke `crontab`.

## launchd

[`launchd.plist.example`](../examples/automation/launchd.plist.example) has an
invalid placeholder label and paths. Copy it to a private location, replace all
placeholders, validate it, and load it explicitly. The package does not call
`launchctl`.

## GitHub Actions

[`github-actions.signal-digest.yml.disabled`](../examples/automation/github-actions.signal-digest.yml.disabled)
uses a `.disabled` suffix and is outside `.github/workflows`, so GitHub will not
run it. It is appropriate only for sources safe to place in the runner's
environment. Avoid it for private feeds unless repository visibility, secrets,
artifacts, logs, and retention have all been reviewed.
