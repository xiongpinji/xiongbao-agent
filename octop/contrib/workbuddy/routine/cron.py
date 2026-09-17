# SPDX-License-Identifier: MIT
"""Minimal 5-field cron matcher (stdlib only, python -S safe).

Fields: minute hour day-of-month month day-of-week
Supports: ``*``, ``n``, ``n-m``, ``*/n``, comma lists.
Does not depend on APScheduler/croniter.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone, tzinfo
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

# Windows often lacks IANA tzdb without the tzdata package.
_FIXED_OFFSETS: dict[str, int] = {
    "UTC": 0,
    "Etc/UTC": 0,
    "Asia/Shanghai": 8,
    "Asia/Hong_Kong": 8,
    "Asia/Singapore": 8,
    "Asia/Tokyo": 9,
    "America/New_York": -5,  # ignore DST for MVP
    "America/Los_Angeles": -8,
    "Europe/London": 0,
}


def resolve_tz(name: str) -> tzinfo:
    """Return a tzinfo for *name*; fall back to fixed offsets when ZoneInfo fails."""
    key = (name or "UTC").strip() or "UTC"
    try:
        return ZoneInfo(key)
    except (ZoneInfoNotFoundError, KeyError, OSError):
        hours = _FIXED_OFFSETS.get(key)
        if hours is None:
            hours = 0
        return timezone(timedelta(hours=hours))


def _parse_field(field: str, minimum: int, maximum: int) -> set[int]:
    field = field.strip()
    if field == "*":
        return set(range(minimum, maximum + 1))
    values: set[int] = set()
    for part in field.split(","):
        part = part.strip()
        if not part:
            continue
        if part.startswith("*/"):
            step = int(part[2:])
            if step <= 0:
                raise ValueError(f"invalid step in cron field: {part}")
            values.update(range(minimum, maximum + 1, step))
            continue
        if "-" in part:
            lo_s, hi_s = part.split("-", 1)
            lo, hi = int(lo_s), int(hi_s)
            if lo > hi:
                raise ValueError(f"invalid range in cron field: {part}")
            values.update(range(lo, hi + 1))
            continue
        values.add(int(part))
    out = {v for v in values if minimum <= v <= maximum}
    if not out:
        raise ValueError(f"cron field empty after parse: {field}")
    return out


def parse_cron(expr: str) -> tuple[set[int], set[int], set[int], set[int], set[int]]:
    """Parse ``m h dom mon dow`` into five value sets."""
    parts = expr.strip().split()
    if len(parts) != 5:
        raise ValueError(f"cron must have 5 fields, got {len(parts)}: {expr!r}")
    minute, hour, dom, month, dow = parts
    minutes = _parse_field(minute, 0, 59)
    hours = _parse_field(hour, 0, 23)
    days = _parse_field(dom, 1, 31)
    months = _parse_field(month, 1, 12)
    dows_raw = _parse_field(dow, 0, 7)
    dows = {(d % 7) for d in dows_raw}
    return minutes, hours, days, months, dows


def matches_cron(expr: str, when: datetime) -> bool:
    """True if *when* (aware or naive local) matches the cron expression."""
    minutes, hours, days, months, dows = parse_cron(expr)
    cron_dow = (when.weekday() + 1) % 7
    return (
        when.minute in minutes
        and when.hour in hours
        and when.day in days
        and when.month in months
        and cron_dow in dows
    )


def local_now(tz_name: str, *, now: datetime | None = None) -> datetime:
    """Current time in *tz_name* (minute resolution for due checks)."""
    tz = resolve_tz(tz_name)
    base = now or datetime.now(timezone.utc)
    if base.tzinfo is None:
        base = base.replace(tzinfo=timezone.utc)
    return base.astimezone(tz).replace(second=0, microsecond=0)


def is_due(
    expr: str,
    *,
    tz_name: str,
    last_fired_at: str | None,
    now: datetime | None = None,
) -> bool:
    """Due when cron matches current local minute and we have not fired this slot."""
    local = local_now(tz_name, now=now)
    if not matches_cron(expr, local):
        return False
    if not last_fired_at:
        return True
    try:
        prev = datetime.fromisoformat(last_fired_at)
    except ValueError:
        return True
    if prev.tzinfo is None:
        prev = prev.replace(tzinfo=timezone.utc)
    prev_local = prev.astimezone(local.tzinfo).replace(second=0, microsecond=0)
    return prev_local < local


def next_match(
    expr: str,
    *,
    tz_name: str,
    after: datetime | None = None,
    limit_hours: int = 48,
) -> datetime | None:
    """Scan forward minute-by-minute for the next match (bounded)."""
    start = local_now(tz_name, now=after) + timedelta(minutes=1)
    for i in range(limit_hours * 60):
        candidate = start + timedelta(minutes=i)
        if matches_cron(expr, candidate):
            return candidate
    return None