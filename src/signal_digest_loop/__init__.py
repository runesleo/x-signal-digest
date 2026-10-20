"""Public API for the offline-first signal digestion loop."""

from .engine import (
    commit_decision,
    create_digest,
    prepare_packet,
    run_cycle,
    submit_feedback,
)
from .errors import ConfigError, ContractError, SignalDigestError

__all__ = [
    "ConfigError",
    "ContractError",
    "SignalDigestError",
    "commit_decision",
    "create_digest",
    "prepare_packet",
    "run_cycle",
    "submit_feedback",
]

__version__ = "0.1.0"
