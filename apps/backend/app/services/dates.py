from datetime import UTC, datetime, time
from zoneinfo import ZoneInfo

import jdatetime

from app.config import get_settings


def local_tz() -> ZoneInfo:
    return ZoneInfo(get_settings().timezone)


def current_jalali_month_bounds(now: datetime | None = None) -> tuple[datetime, datetime]:
    """UTC [start, end) of the current Jalali (Shamsi) month in the configured timezone."""
    tz = local_tz()
    local_now = (now or datetime.now(UTC)).astimezone(tz)
    jtoday = jdatetime.date.fromgregorian(date=local_now.date())
    start_j = jdatetime.date(jtoday.year, jtoday.month, 1)
    next_j = (
        jdatetime.date(jtoday.year + 1, 1, 1)
        if jtoday.month == 12
        else jdatetime.date(jtoday.year, jtoday.month + 1, 1)
    )
    start = datetime.combine(start_j.togregorian(), time.min, tzinfo=tz).astimezone(UTC)
    end = datetime.combine(next_j.togregorian(), time.min, tzinfo=tz).astimezone(UTC)
    return start, end
