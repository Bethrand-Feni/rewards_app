from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

try:
    import js
    from pyodide.ffi import to_js
except ImportError:  # Normal CPython uses the host's IANA timezone database.
    js = None
    to_js = None


def _worker_parts(value: datetime, timezone: str) -> tuple[int, int, int, int, int]:
    options = to_js(
        {
            "timeZone": timezone,
            "year": "numeric",
            "month": "2-digit",
            "day": "2-digit",
            "hour": "2-digit",
            "minute": "2-digit",
            "hourCycle": "h23",
        },
        dict_converter=js.Object.fromEntries,
    )
    formatter = js.Intl.DateTimeFormat.new("en-CA", options)
    parts = formatter.formatToParts(js.Date.new(value.timestamp() * 1000)).to_py()
    values = {part["type"]: part["value"] for part in parts}
    return tuple(int(values[key]) for key in ("year", "month", "day", "hour", "minute"))


def timezone_is_valid(timezone: str) -> bool:
    try:
        if js is not None:
            options = to_js(
                {"timeZone": timezone},
                dict_converter=js.Object.fromEntries,
            )
            js.Intl.DateTimeFormat.new("en", options)
        else:
            ZoneInfo(timezone)
        return True
    except Exception:
        return False


def weekday_selected(mask: int, value: date) -> bool:
    """Monday is bit 0 and Sunday is bit 6."""
    return bool(mask & (1 << value.weekday()))


def scheduled_for_date(
    schedule_type: str,
    start_date: date,
    weekday_mask: int,
    candidate: date,
) -> bool:
    if candidate < start_date:
        return False
    if schedule_type == "DAILY":
        return True
    if schedule_type == "WEEKDAYS":
        return candidate.weekday() < 5
    if schedule_type == "WEEKENDS":
        return candidate.weekday() >= 5
    if schedule_type == "WEEKLY":
        return (candidate - start_date).days % 7 == 0
    if schedule_type == "MONTHLY":
        return candidate.day == start_date.day
    if schedule_type == "LEGACY_WEEKDAYS":
        return weekday_selected(weekday_mask, candidate)
    if schedule_type == "ONCE":
        return candidate == start_date
    return False


def occurrence_dates(
    schedule_type: str,
    start_date: date,
    weekday_mask: int,
    local_today: date,
    horizon_days: int = 7,
) -> list[date]:
    candidates = (local_today + timedelta(days=offset) for offset in range(horizon_days + 1))
    return [
        candidate
        for candidate in candidates
        if scheduled_for_date(schedule_type, start_date, weekday_mask, candidate)
    ]


def due_at_utc(local_date: date, local_time: str, timezone: str) -> datetime:
    hours, minutes = (int(part) for part in local_time.split(":"))
    if js is not None:
        desired = datetime(
            local_date.year,
            local_date.month,
            local_date.day,
            hours,
            minutes,
            tzinfo=UTC,
        )
        candidate = desired
        # Two passes handle offsets that change around daylight-saving transitions.
        for _ in range(2):
            observed = datetime(*_worker_parts(candidate, timezone), tzinfo=UTC)
            candidate = desired - (observed - candidate)
        return candidate
    local = datetime.combine(local_date, time(hours, minutes), ZoneInfo(timezone))
    return local.astimezone(UTC)


def local_today(now: datetime, timezone: str) -> date:
    if js is not None:
        year, month, day, _, _ = _worker_parts(now, timezone)
        return date(year, month, day)
    return now.astimezone(ZoneInfo(timezone)).date()
