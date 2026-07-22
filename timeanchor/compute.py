"""Resolve-in-code datetime helpers.

The half of :mod:`timeanchor` that never touches the prompt: given a timezone
and a reference instant, compute the *actual* :class:`datetime.date` /
:class:`datetime.datetime` values so the model is handed pre-resolved answers
instead of doing weekday arithmetic itself.
"""

from __future__ import annotations

from datetime import date, datetime, time
from zoneinfo import ZoneInfo

__all__ = [
    "parse_weekday",
    "next_weekday",
    "in_days",
    "at_local",
    "to_utc",
    "to_local",
    "format_local",
    "now_in",
]

# Monday == 0 to match date.weekday().
_WEEKDAY_INDEX: dict[str, int] = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}

# Common three-letter abbreviations map onto the same indices.
_WEEKDAY_ALIASES: dict[str, int] = {
    name[:3]: idx for name, idx in _WEEKDAY_INDEX.items()
}

WEEKDAY_NAMES: tuple[str, ...] = (
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
)


def _zone(tz: str) -> ZoneInfo:
    try:
        return ZoneInfo(tz)
    except Exception as exc:  # ZoneInfoNotFoundError and friends
        raise ValueError(
            f"Unknown timezone {tz!r}. Use an IANA name like 'Asia/Kolkata' "
            f"or 'America/New_York'."
        ) from exc


def now_in(tz: str = "UTC", now: datetime | None = None) -> datetime:
    """Return an aware ``datetime`` in ``tz``.

    If ``now`` is given it is converted into ``tz`` (it must be timezone-aware,
    so results are deterministic in tests). Otherwise the current wall-clock
    time in ``tz`` is used.
    """

    zone = _zone(tz)
    if now is None:
        return datetime.now(zone)
    if now.tzinfo is None:
        raise ValueError(
            "now must be timezone-aware; pass e.g. "
            "datetime(2026, 7, 22, 17, 15, tzinfo=ZoneInfo('Asia/Kolkata'))."
        )
    return now.astimezone(zone)


def parse_weekday(name: str) -> int:
    """Parse a weekday name into an index where Monday is ``0``.

    Accepts full names and three-letter abbreviations, case-insensitively:
    ``"friday"``, ``"Fri"``, ``"FRIDAY"`` all return ``4``.
    """

    if not isinstance(name, str):
        raise TypeError(f"weekday name must be a string, got {type(name).__name__}")
    key = name.strip().lower()
    if key in _WEEKDAY_INDEX:
        return _WEEKDAY_INDEX[key]
    if key in _WEEKDAY_ALIASES:
        return _WEEKDAY_ALIASES[key]
    raise ValueError(
        f"Unknown weekday {name!r}. Expected one of "
        f"{', '.join(WEEKDAY_NAMES)} (or a three-letter abbreviation)."
    )


def next_weekday(
    name: str,
    tz: str = "UTC",
    now: datetime | None = None,
    strict_next: bool = False,
) -> date:
    """Return the date of the coming occurrence of a weekday.

    By default, if today *is* the named weekday, today is returned (offset 0).
    Set ``strict_next=True`` to always skip to the following week's occurrence
    (offset 7 when today matches) — useful when a user says "next Friday" and
    means the one after today even if today is Friday.
    """

    target = parse_weekday(name)
    today = now_in(tz, now).date()
    delta = (target - today.weekday()) % 7
    if strict_next and delta == 0:
        delta = 7
    return today + _days(delta)


def in_days(n: int, tz: str = "UTC", now: datetime | None = None) -> date:
    """Return the local date ``n`` days from the reference instant in ``tz``."""

    return now_in(tz, now).date() + _days(n)


def at_local(
    date_or_str: date | str,
    hhmm: str,
    tz: str = "UTC",
) -> datetime:
    """Build a timezone-aware ``datetime`` from a local date and ``"HH:MM"``.

    ``date_or_str`` may be a :class:`datetime.date` or an ISO ``"YYYY-MM-DD"``
    string. The returned datetime carries ``tz`` as its tzinfo, so wall-clock
    times land where the user actually lives.
    """

    the_date = _coerce_date(date_or_str)
    parsed = _parse_hhmm(hhmm)
    return datetime.combine(the_date, parsed, tzinfo=_zone(tz))


def to_utc(dt: datetime) -> datetime:
    """Convert an aware ``datetime`` to UTC. Naive input is rejected."""

    if dt.tzinfo is None:
        raise ValueError("to_utc requires a timezone-aware datetime.")
    return dt.astimezone(ZoneInfo("UTC"))


def to_local(dt: datetime, tz: str) -> datetime:
    """Convert an aware ``datetime`` into ``tz``. Naive input is rejected."""

    if dt.tzinfo is None:
        raise ValueError("to_local requires a timezone-aware datetime.")
    return dt.astimezone(_zone(tz))


def format_local(dt: datetime, tz: str) -> str:
    """Format an instant in the *user's* timezone, the anti-"UTC echo" helper.

    Produces strings like ``"Fri, Jul 24 at 9:00 AM IST"`` — a weekday, a
    human date, a 12-hour time, and the local zone abbreviation — so the model
    never reads a bare UTC timestamp back to someone living elsewhere.
    """

    local = to_local(dt, tz)
    hour12 = local.strftime("%I").lstrip("0") or "0"
    minute = local.strftime("%M")
    ampm = local.strftime("%p")
    abbrev = local.tzname() or tz
    return (
        f"{local.strftime('%a')}, {local.strftime('%b')} {local.day} "
        f"at {hour12}:{minute} {ampm} {abbrev}"
    )


def _days(n: int):
    from datetime import timedelta

    return timedelta(days=n)


def _coerce_date(value: date | str) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value.strip())
        except ValueError as exc:
            raise ValueError(
                f"Expected an ISO date 'YYYY-MM-DD', got {value!r}."
            ) from exc
    raise TypeError(
        f"date_or_str must be a date or 'YYYY-MM-DD' string, "
        f"got {type(value).__name__}"
    )


def _parse_hhmm(hhmm: str) -> time:
    if not isinstance(hhmm, str):
        raise TypeError(f"time must be a 'HH:MM' string, got {type(hhmm).__name__}")
    parts = hhmm.strip().split(":")
    if len(parts) != 2:
        raise ValueError(f"Expected time as 'HH:MM', got {hhmm!r}.")
    try:
        hour, minute = int(parts[0]), int(parts[1])
    except ValueError as exc:
        raise ValueError(f"Expected numeric 'HH:MM', got {hhmm!r}.") from exc
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError(f"Time out of range in {hhmm!r} (need 00:00–23:59).")
    return time(hour, minute)
