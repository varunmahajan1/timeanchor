"""timeanchor — deterministic time grounding for LLM prompts.

LLMs are bad at time. They do DIY weekday arithmetic and get "next Friday"
wrong, echo UTC timestamps at users who live in other zones, and cheerfully
schedule things in the past. ``timeanchor`` fixes this two ways:

1. Put a *precomputed* date-anchor table in the prompt so the model never
   derives a weekday itself (:func:`anchor_block`).
2. Resolve real datetimes in *code* and hand the model pre-resolved values
   (:func:`next_weekday`, :func:`at_local`, :func:`to_utc`, ...).

Stdlib only — :mod:`datetime` and :mod:`zoneinfo`.

Example
-------
>>> from datetime import datetime
>>> from zoneinfo import ZoneInfo
>>> from timeanchor import anchor_block, next_weekday, at_local, format_local
>>> now = datetime(2026, 7, 22, 17, 15, tzinfo=ZoneInfo("Asia/Kolkata"))
>>> print(anchor_block(tz="Asia/Kolkata", days=14, now=now))  # doctest: +ELLIPSIS
## Current date & time
Today is Wednesday, 2026-07-22. Local time: 17:15 (Asia/Kolkata, UTC+05:30).
...
>>> friday = next_weekday("friday", tz="Asia/Kolkata", now=now)
>>> friday.isoformat()
'2026-07-24'
>>> reminder = at_local(friday, "09:00", tz="Asia/Kolkata")
>>> format_local(reminder, tz="Asia/Kolkata")
'Fri, Jul 24 at 9:00 AM IST'
"""

from __future__ import annotations

from .anchors import anchor_block
from .compute import (
    at_local,
    format_local,
    in_days,
    next_weekday,
    now_in,
    parse_weekday,
    to_local,
    to_utc,
)

__version__ = "0.1.0"

__all__ = [
    "anchor_block",
    "next_weekday",
    "in_days",
    "at_local",
    "to_utc",
    "to_local",
    "format_local",
    "parse_weekday",
    "now_in",
    "__version__",
]
