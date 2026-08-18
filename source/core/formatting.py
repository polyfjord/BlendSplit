"""Formatting helpers shared by Blender UI and tests."""

from __future__ import annotations

def format_time(time_ns: int | None, decimals: int = 2, placeholder: str = "—") -> str:
    """Format nanoseconds as a compact speedrun time."""
    if time_ns is None or time_ns < 0:
        return placeholder

    decimals = max(0, min(3, int(decimals)))
    units_per_second = 10**decimals
    total_units = (time_ns * units_per_second + 500_000_000) // 1_000_000_000
    total_seconds, fractional_units = divmod(total_units, units_per_second)
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    seconds_text = f"{seconds:02d}"
    if decimals:
        seconds_text += f".{fractional_units:0{decimals}d}"
    if hours:
        return f"{hours}:{minutes:02d}:{seconds_text}"
    return f"{minutes:02d}:{seconds_text}"


def format_delta(delta_ns: int | None, decimals: int = 2) -> str:
    """Format a signed comparison delta."""
    if delta_ns is None:
        return ""
    sign = "−" if delta_ns < 0 else "+"
    formatted_time = format_time(abs(delta_ns), decimals=decimals)

    # Keeps "nescessary" Zeroes for user readability
    if formatted_time.startswith("00:"):
        formatted_time = formatted_time[3:]
    
    return sign + formatted_time
