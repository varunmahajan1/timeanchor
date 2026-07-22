# timeanchor

**Deterministic time grounding for LLM prompts.** Stop your agent from thinking today is Tuesday.

Zero dependencies — Python stdlib (`datetime` + `zoneinfo`) only.

---

## The problem: your agent thinks today is Tuesday

Language models are confidently, subtly wrong about time. Three failure modes show up again and again in production:

1. **DIY weekday arithmetic.** Ask a model for "next Friday" and it will happily count on its fingers — off by one, off by a week, or anchored to a date it hallucinated. It doesn't *know* what day it is unless you tell it, and even when you tell it the date, it still miscomputes the weekday.
2. **UTC echo.** You store timestamps in UTC (good), the model reads `2026-07-24T03:30:00Z` back to a user in Mumbai (bad), and now "your reminder is set for 3:30" means nothing to someone whose clock says 9:00 AM.
3. **Scheduling in the past.** Without a hard anchor for "now," models cheerfully schedule things for this morning, or for a Friday that already happened.

I hit all three running a production AI assistant. Users would say "remind me next Friday at 9" and get a reminder on the wrong day, described in a timezone they don't live in. The root cause is always the same: **the model was asked to do date math it isn't reliable at.**

## The fix: never let the model derive a date

`timeanchor` splits the job in two, and takes both halves away from the model:

1. **Anchor the prompt.** Drop a precomputed date table into the system prompt so the model *reads* the weekday for any upcoming day instead of deriving it. This is `anchor_block()`.
2. **Resolve in code.** When you actually need a datetime — to store a reminder, call an API, set a cron — compute it in Python and hand the model the finished value. This is `next_weekday()`, `at_local()`, `to_utc()`, `format_local()`, and friends.

The model's only remaining job is to pick *which* anchor the user meant. That, it's good at.

```bash
pip install timeanchor
```

```python
from datetime import datetime
from zoneinfo import ZoneInfo
from timeanchor import anchor_block, next_weekday, at_local, to_utc, format_local

now = datetime(2026, 7, 22, 17, 15, tzinfo=ZoneInfo("Asia/Kolkata"))

# 1. Put this in your system prompt, regenerated each turn:
print(anchor_block(tz="Asia/Kolkata", now=now))

# 2. Resolve the datetime in code once the model picks a day:
friday = next_weekday("friday", tz="Asia/Kolkata", now=now)   # date(2026, 7, 24)
reminder = at_local(friday, "09:00", tz="Asia/Kolkata")       # aware datetime
store_utc = to_utc(reminder).isoformat()                      # '2026-07-24T03:30:00+00:00'
tell_user = format_local(reminder, "Asia/Kolkata")            # 'Fri, Jul 24 at 9:00 AM IST'
```

## What `anchor_block()` looks like

```
## Current date & time
Today is Wednesday, 2026-07-22. Local time: 17:15 (Asia/Kolkata, UTC+05:30).

## Date anchors (use these — never derive weekdays yourself)
Today       Wed 2026-07-22  (today)
Tomorrow    Thu 2026-07-23  (this Thursday, tomorrow)
Fri         Fri 2026-07-24  (this Friday, in 2 days)
Sat         Sat 2026-07-25  (this Saturday, in 3 days)
Sun         Sun 2026-07-26  (this Sunday, in 4 days)
Mon         Mon 2026-07-27  (this Monday, in 5 days)
Tue         Tue 2026-07-28  (this Tuesday, in 6 days)
Wed         Wed 2026-07-29  (next Wednesday, in 7 days)
...through day 14
Wed         Wed 2026-08-05  (in 14 days)

## "this" vs "next" (this = the coming one; next = the week after)
this Monday    = Mon 2026-07-27    next Monday    = Mon 2026-08-03
this Friday    = Fri 2026-07-24    next Friday    = Fri 2026-07-31
...
```

The `this`/`next` disambiguation is spelled out because it's the single most common source of scheduling bugs: "next Friday" means different things to different people. `timeanchor` states the convention — **this = the coming occurrence, next = the one after that** — right in the prompt, so the model applies it consistently instead of guessing per turn.

## Before / after

**Before** — the model computes, and gets it wrong:

```
System: Today is 2026-07-22.
User:   Remind me next Friday at 9am.
Model:  Sure — I'll remind you on Friday, July 25th.   ← wrong day AND wrong week
```

**After** — the model reads an anchor, code resolves the datetime:

```
System: [anchor_block output — Fri = Fri 2026-07-24, next Friday = Fri 2026-07-31]
User:   Remind me next Friday at 9am.
Model:  Setting it for {next_weekday("friday", strict_next=True)} → 2026-07-31.
        → at_local("2026-07-31", "09:00", "Asia/Kolkata") → stored as UTC
        → "Fri, Jul 31 at 9:00 AM IST"                    ← right day, user's timezone
```

## Integration: regenerate the anchor each turn

The anchor is a few hundred bytes and costs nothing to rebuild, so regenerate it on every request rather than caching a stale "today." Place it at a **stable position** in your prompt (e.g. right after your static system preamble) so everything above it stays byte-identical across turns and your provider's prompt cache still hits.

```python
from timeanchor import anchor_block

def build_system_prompt(user_tz: str) -> str:
    return "\n\n".join([
        STATIC_PREAMBLE,           # unchanging — stays cached
        anchor_block(tz=user_tz),  # regenerated per turn, at a stable offset
    ])
```

FastAPI agent loop:

```python
from fastapi import FastAPI
from timeanchor import anchor_block, next_weekday, at_local, to_utc

app = FastAPI()

@app.post("/chat")
async def chat(req: ChatRequest):
    system = build_system_prompt(req.user_tz)          # includes a fresh anchor_block
    reply = await llm.complete(system=system, messages=req.messages)

    # When the model asks to schedule, resolve in code — never trust its datetime:
    if reply.tool_call == "set_reminder":
        day = next_weekday(reply.args["weekday"], tz=req.user_tz,
                           strict_next=reply.args.get("qualifier") == "next")
        when = at_local(day, reply.args["time"], tz=req.user_tz)
        await reminders.create(user=req.user_id, at=to_utc(when))
    return reply
```

## API reference

| Function | Returns | What it does |
| --- | --- | --- |
| `anchor_block(tz="UTC", days=14, now=None)` | `str` | The headline: a prompt-ready date-anchor block — today's date/time, a table through `days` ahead, and a this/next disambiguation section. |
| `next_weekday(name, tz="UTC", now=None, strict_next=False)` | `date` | The coming occurrence of a weekday. `strict_next=True` always skips today. |
| `in_days(n, tz="UTC", now=None)` | `date` | The local date `n` days from now. |
| `at_local(date_or_str, "HH:MM", tz="UTC")` | aware `datetime` | Build a timezone-aware datetime from a local date + wall-clock time. |
| `to_utc(dt)` | aware `datetime` | Convert an aware datetime to UTC (for storage). |
| `to_local(dt, tz)` | aware `datetime` | Convert an aware datetime into a target zone. |
| `format_local(dt, tz)` | `str` | Human formatting in the **user's** zone — `"Fri, Jul 24 at 9:00 AM IST"`. The anti-UTC-echo helper. |
| `parse_weekday(name)` | `int` | Weekday name/abbrev → index (Mon=0), with friendly errors. |
| `now_in(tz="UTC", now=None)` | aware `datetime` | The reference instant in a zone; the basis every helper shares. |

Every function takes an optional `now` (an aware `datetime`) so your tests are deterministic and your production code stays honest about "now."

## Design notes

- **Stdlib only.** `datetime` + `zoneinfo`. No `pytz`, no `dateutil`, nothing to audit or pin.
- **Aware or bust.** Naive datetimes are rejected at the door. Timezone bugs come from mixing aware and naive values; `timeanchor` refuses to.
- **DST-correct.** Because everything runs through `zoneinfo`, a 9:00 AM wall-clock reminder is 9:00 AM whether or not a DST switch happened in between — the UTC offset moves, the local time doesn't.
- **Deterministic.** Same `now`, same output, every time. That's what makes the tests golden-able and the anchors cache-friendly.

## Running the tests

```bash
python3 -m pytest -q          # if pytest is installed
python3 -m unittest discover -s tests   # stdlib fallback, no dependencies
```

## License

MIT © 2026 Varun Mahajan

## Related projects

Part of a small family of zero-drama building blocks for LLM apps:

- [llm-meter](https://github.com/varunmahajan1/llm-meter) — token cost tracking + rate limiting
- [agent-runtime](https://github.com/varunmahajan1/agent-runtime) — a minimal agent execution loop
- [agent-stream](https://github.com/varunmahajan1/agent-stream) — streaming primitives for agent output
- [promptshield](https://github.com/varunmahajan1/promptshield) — prompt-injection guardrails
- [llm-failover](https://github.com/varunmahajan1/llm-failover) — provider failover and retries
- [ssrfguard](https://github.com/varunmahajan1/ssrfguard) — SSRF protection for tool-calling agents
- [channelfmt](https://github.com/varunmahajan1/channelfmt) — format messages per channel (WhatsApp, Slack, ...)
