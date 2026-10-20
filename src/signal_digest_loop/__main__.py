"""Allow ``python -m signal_digest_loop`` to run the CLI."""

from .cli import main


raise SystemExit(main())
