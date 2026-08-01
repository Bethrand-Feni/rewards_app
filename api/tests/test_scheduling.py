from datetime import UTC, date, datetime

from app.scheduling import due_at_utc, occurrence_dates, timezone_is_valid, weekday_selected


def test_weekday_mask_uses_monday_as_bit_zero():
    assert weekday_selected(1, date(2026, 8, 3))
    assert not weekday_selected(1, date(2026, 8, 4))
    assert weekday_selected(64, date(2026, 8, 2))


def test_daily_and_selected_weekday_occurrences():
    today = date(2026, 8, 3)
    assert occurrence_dates("DAILY", today, 0, today, 2) == [
        date(2026, 8, 3),
        date(2026, 8, 4),
        date(2026, 8, 5),
    ]
    monday_wednesday = 1 | 4
    assert occurrence_dates("LEGACY_WEEKDAYS", today, monday_wednesday, today, 4) == [
        date(2026, 8, 3),
        date(2026, 8, 5),
    ]


def test_named_schedule_frequencies():
    monday = date(2026, 8, 3)
    assert occurrence_dates("WEEKDAYS", monday, 0, monday, 6) == [
        date(2026, 8, 3),
        date(2026, 8, 4),
        date(2026, 8, 5),
        date(2026, 8, 6),
        date(2026, 8, 7),
    ]
    assert occurrence_dates("WEEKENDS", monday, 0, monday, 6) == [
        date(2026, 8, 8),
        date(2026, 8, 9),
    ]
    assert occurrence_dates("WEEKLY", monday, 0, monday, 14) == [
        date(2026, 8, 3),
        date(2026, 8, 10),
        date(2026, 8, 17),
    ]
    assert occurrence_dates(
        "MONTHLY", date(2026, 8, 5), 0, date(2026, 9, 1), 7
    ) == [date(2026, 9, 5)]


def test_johannesburg_due_time_converts_to_utc():
    assert due_at_utc(date(2026, 8, 3), "18:30", "Africa/Johannesburg") == datetime(
        2026, 8, 3, 16, 30, tzinfo=UTC
    )


def test_timezone_validation():
    assert timezone_is_valid("Africa/Johannesburg")
    assert not timezone_is_valid("Not/A_Timezone")
