class AutoDARError(Exception):
    """A user-facing application error."""


class ConfigurationError(AutoDARError):
    """Configuration or employee data is invalid."""


class ReportError(AutoDARError):
    """A report could not be generated."""

