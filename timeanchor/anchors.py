"""Prompt-ready date-anchor rendering.

:func:`anchor_block` produces the compact block you paste into a system prompt
so the model reads today's weekday and a table of upcoming dates instead of
computing them. Regenerate it per turn — it is a few hundred bytes and, kept at
a stable prompt position, plays nicely with prompt caching.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from .compute import WEEKDAY_NAMES, now_in

__all__ = ["anchor_block"]


def _utc_offset(dt: datetime) -> str:
    raw = dt.strftime("%z")  # e.g. "+0530"
    if not raw:
        return "UTC+00:00"
    sign, hh, mm = raw[0], raw[1:3], raw[3:5]
    return f"UTC{sign}{hh}:{mm}"


def _relative(offset: int) -> str:
    if offset == 0:
        return "today"
    if offset == 1:
        return "tomorrow"
    return f"in {offset} days"


def _this_next_dates(today: date) -> dict[str, tuple[date, date]]:
    """For each weekday, the ("this", "next") date pair.

    Convention: "this X" is the coming X (today itself when today is that
    weekday); "next X" is the following week's X, always seven days later.
    """

    pairs: dict[str, tuple[date, date]] = {}
    for target, full_name in enumerate(WEEKDAY_NAMES):
        delta = (target - today.weekday()) % 7
        this_date = today + timedelta(days=delta)
        pairs[full_name] = (this_date, this_date + timedelta(days=7))
    return pairs


def anchor_block(
    tz: str = "UTC",
    days: int = 14,
    now: datetime | None = None,
) -> str:
    """Render a prompt-ready date-anchor block.

    Parameters
    ----------
    tz:
        IANA timezone name the anchors are expressed in (e.g. ``"Asia/Kolkata"``).
    days:
        How many days ahead to tabulate. The table runs from today (offset 0)
        through ``days`` inclusive.
    now:
        Reference instant for determinism/tests — an aware ``datetime``. When
        omitted, the current time in ``tz`` is used.

    Returns
    -------
    str
        A multi-section Markdown block: the current date/time line, the anchor
        table, and an explicit "this" vs "next" disambiguation section.
    """

    if days < 1:
        raise ValueError("days must be at least 1.")

    local = now_in(tz, now)
    today = local.date()
    offset_str = _utc_offset(local)

    header = (
        f"Today is {WEEKDAY_NAMES[today.weekday()]}, {today.isoformat()}. "
        f"Local time: {local.strftime('%H:%M')} ({tz}, {offset_str})."
    )

    this_next = _this_next_dates(today)

    rows: list[str] = []
    for offset in range(days + 1):
        d = today + timedelta(days=offset)
        full_name = WEEKDAY_NAMES[d.weekday()]
        abbrev = full_name[:3]

        if offset == 0:
            key = "Today"
        elif offset == 1:
            key = "Tomorrow"
        else:
            key = abbrev

        this_date, next_date = this_next[full_name]
        notes: list[str] = []
        if offset != 0:
            if d == this_date:
                notes.append(f"this {full_name}")
            elif d == next_date:
                notes.append(f"next {full_name}")
        notes.append(_relative(offset))

        rows.append(
            f"{key:<12}{abbrev} {d.isoformat()}  ({', '.join(notes)})"
        )

    # Disambiguation section: nail down this/next per weekday, unambiguously.
    disambig: list[str] = []
    for full_name in WEEKDAY_NAMES:
        this_date, next_date = this_next[full_name]
        disambig.append(
            f"this {full_name:<9} = {this_date.strftime('%a')} {this_date.isoformat()}"
            f"    next {full_name:<9} = {next_date.strftime('%a')} {next_date.isoformat()}"
        )

    return "\n".join(
        [
            "## Current date & time",
            header,
            "",
            "## Date anchors (use these — never derive weekdays yourself)",
            *rows,
            "",
            '## "this" vs "next" (this = the coming one; next = the week after)',
            *disambig,
        ]
    )
