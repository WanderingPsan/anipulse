"""Small pure functions that turn messy source text into clean single values.

Pure means: no database, no network, no files. The same input always gives the same output,
which is why each function can be tested with one line.
"""

import math
import re
from datetime import datetime
from typing import Any

import pandas as pd

# "1 hr 55 min" -> hr=1, min=55. Each unit is optional, and "min." with a dot also matches.
_DURATION_PART = re.compile(r"(\d+)\s*(hr|min|sec)")

# The rule for filling a missing season from the air date's month.
_SEASON_BY_MONTH = {
    1: "winter",
    2: "winter",
    3: "winter",
    4: "spring",
    5: "spring",
    6: "spring",
    7: "summer",
    8: "summer",
    9: "summer",
    10: "fall",
    11: "fall",
    12: "fall",
}
VALID_SEASONS = frozenset(_SEASON_BY_MONTH.values())

# Company names that contain a comma, like "NIS America, Inc.", get cut in two when a cell
# is split on ", ". A piece that is only one of these legal suffixes belongs to the name
# before it.
_COMPANY_SUFFIXES = frozenset({"Inc.", "Inc", "Ltd.", "Ltd", "LLC", "LLC."})


def is_missing(value: Any) -> bool:
    """True for None, NaN, pandas' NA, and blank strings: every way a cell can be empty."""
    if isinstance(value, str):
        return value.strip() == ""
    return value is None or bool(pd.isna(value))


def clean_text(value: Any) -> str | None:
    """Return the text stripped of spaces, or None when the cell is empty."""
    if is_missing(value):
        return None
    return str(value).strip()


def clean_int(value: Any) -> int | None:
    """Return a whole number, or None. Accepts 28, 28.0, and "28"."""
    if is_missing(value):
        return None
    return int(float(value))


def clean_float(value: Any) -> float | None:
    """Return a decimal number, or None."""
    if is_missing(value):
        return None
    number = float(value)
    return None if math.isnan(number) else number


def parse_duration(text: Any) -> int | None:
    """Turn "24 min per ep" or "1 hr 55 min" into minutes per episode.

    Seconds count too: "30 sec per ep" is half a minute, which rounds to 1 so a very short
    episode is never stored as 0 minutes. "Unknown" and empty cells give None.
    """
    cleaned = clean_text(text)
    if cleaned is None:
        return None
    parts = _DURATION_PART.findall(cleaned)
    if not parts:
        return None
    seconds = 0
    for amount, unit in parts:
        seconds += int(amount) * {"hr": 3600, "min": 60, "sec": 1}[unit]
    if seconds == 0:
        return None
    return max(1, round(seconds / 60))


def parse_aired_from(text: Any) -> datetime | None:
    """Read an ISO date like "2023-09-29T00:00:00+00:00", or None if empty or unreadable."""
    cleaned = clean_text(text)
    if cleaned is None:
        return None
    try:
        return datetime.fromisoformat(cleaned)
    except ValueError:
        return None


def parse_year(year: Any, aired_from: Any) -> int | None:
    """Keep the source's year; when it is missing, use the year the anime started airing."""
    known = clean_int(year)
    if known is not None:
        return known
    aired = parse_aired_from(aired_from)
    return aired.year if aired else None


def parse_season(season: Any, aired_from: Any) -> str | None:
    """Keep the source's season; when it is missing, derive it from the start month.

    January to March is winter, April to June spring, July to September summer, and
    October to December fall. A season we do not recognize counts as missing.
    """
    known = clean_text(season)
    if known is not None and known.lower() in VALID_SEASONS:
        return known.lower()
    aired = parse_aired_from(aired_from)
    return _SEASON_BY_MONTH[aired.month] if aired else None


def split_list_field(text: Any) -> list[str]:
    """Turn "Action, Adventure" into ["Action", "Adventure"].

    "Unknown", empty, and NaN cells become an empty list, because "we do not know any
    genres" and "no genres" are stored the same way: no join rows.
    """
    cleaned = clean_text(text)
    if cleaned is None or cleaned.lower() == "unknown":
        return []
    return [part.strip() for part in cleaned.split(",") if part.strip()]


def split_company_field(text: Any) -> list[str]:
    """Like split_list_field, but glues legal suffixes back on: "NIS America, Inc." stays whole."""
    names: list[str] = []
    for piece in split_list_field(text):
        if piece in _COMPANY_SUFFIXES and names:
            names[-1] = f"{names[-1]}, {piece}"
        else:
            names.append(piece)
    return names
