from datetime import datetime, timezone


def utcnow() -> datetime:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc)


__all__ = ["utcnow"]
