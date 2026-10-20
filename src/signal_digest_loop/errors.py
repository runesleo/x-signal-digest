"""Domain-specific exceptions raised by :mod:`signal_digest_loop`."""


class SignalDigestError(Exception):
    """Base class for expected, user-actionable failures."""


class ConfigError(SignalDigestError):
    """The TOML configuration is missing or invalid."""


class ContractError(SignalDigestError):
    """A packet, decision, analyzer response, or transaction is invalid."""
