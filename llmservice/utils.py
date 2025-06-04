
from datetime import datetime, timezone


def _now_dt() -> datetime:
    """Current UTC time with microsecond precision."""
    return datetime.now(timezone.utc)