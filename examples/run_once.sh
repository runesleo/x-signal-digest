#!/bin/sh
set -eu

# Run from the project root after `python -m pip install -e .`.
# Omit --apply for a dry, non-committing preview.
signal-digest cycle --config examples/config.toml --allow-command-analyzer --apply
