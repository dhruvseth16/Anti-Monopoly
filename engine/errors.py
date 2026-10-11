"""Shared exceptions — Hard Rule 5 (null safety)."""


class MissingDataError(Exception):
    """A config field needed for this calculation is still null (not digitised yet)."""


def require(value, label: str):
    """Return value, or raise MissingDataError if it is None. Never invent a number."""
    if value is None:
        raise MissingDataError(f"{label} is null in config - digitise it before this code path can run")
    return value
