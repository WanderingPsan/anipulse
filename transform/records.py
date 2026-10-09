"""Turn one source row (a CSV row or an API anime) into one clean record.

Both sources end up in the same shape, so the loader does not care where a record came from.
A record is a dict with:
- every `anime` table column except updated_at (the loader stamps that),
- "tags": tag names from genres, explicit_genres, themes, and demographics,
- "companies": CompanyRef entries for studios, producers, and licensors.
"""

from typing import Any, NamedTuple

from transform.parsing import (
    clean_float,
    clean_int,
    clean_text,
    parse_duration,
    parse_season,
    parse_year,
    split_company_field,
    split_list_field,
)

# The anime table's columns, in table order. The loader uses this to pick them out.
ANIME_COLUMNS = (
    "mal_id",
    "title",
    "title_english",
    "type",
    "source",
    "episodes",
    "duration_min",
    "rating",
    "synopsis",
    "season",
    "year",
    "broadcast_day",
    "broadcast_time",
    "status",
    "score",
    "scored_by",
    "members",
    "favorites",
    "data_source",
)

TAG_FIELDS = ("genres", "explicit_genres", "themes", "demographics")
# Source field name -> the role we store in anime_companies.
COMPANY_ROLES = {"studios": "studio", "producers": "producer", "licensors": "licensor"}


class CompanyRef(NamedTuple):
    """One company credited on one anime. mal_id is None when the source only gives a name."""

    name: str
    role: str
    mal_id: int | None = None


def _build_record(
    fields: dict[str, Any], tags: list[str], companies: list[CompanyRef], data_source: str
) -> dict[str, Any]:
    """Clean the flat fields both sources share. Keeping this in one place keeps them in sync."""
    return {
        "mal_id": clean_int(fields["mal_id"]),
        "title": clean_text(fields["title"]),
        "title_english": clean_text(fields["title_english"]),
        "type": clean_text(fields["type"]),
        "source": clean_text(fields["source"]),
        "episodes": clean_int(fields["episodes"]),
        "duration_min": parse_duration(fields["duration"]),
        "rating": clean_text(fields["rating"]),
        "synopsis": clean_text(fields["synopsis"]),
        "season": parse_season(fields["season"], fields["aired_from"]),
        "year": parse_year(fields["year"], fields["aired_from"]),
        "broadcast_day": clean_text(fields["broadcast_day"]),
        "broadcast_time": clean_text(fields["broadcast_time"]),
        "status": clean_text(fields["status"]),
        "score": clean_float(fields["score"]),
        "scored_by": clean_int(fields["scored_by"]),
        "members": clean_int(fields["members"]),
        "favorites": clean_int(fields["favorites"]),
        "data_source": data_source,
        "tags": tags,
        "companies": companies,
    }


def kaggle_row_to_record(row: dict[str, Any]) -> dict[str, Any]:
    """Turn one row of the Kaggle CSV (as a dict) into a record.

    The CSV is already flat and uses the API's field names, so only the list cells need work:
    "Adventure, Drama, Fantasy" becomes three tag names.
    """
    tags = [name for field in TAG_FIELDS for name in split_list_field(row.get(field))]
    companies = [
        CompanyRef(name, role)
        for field, role in COMPANY_ROLES.items()
        for name in split_company_field(row.get(field))
    ]
    return _build_record(row, tags, companies, data_source="kaggle")


def _names(items: list[dict[str, Any]] | None) -> list[str]:
    """[{"mal_id": 2, "name": "Adventure"}, ...] -> ["Adventure", ...]."""
    return [item["name"] for item in items or []]


def flatten_jikan_anime(raw: dict[str, Any]) -> dict[str, Any]:
    """Turn one anime from the API (Jikan v4 shape) into a record.

    The API nests some fields: aired is {"from": ...}, broadcast is {"day": ..., "time": ...},
    and the list fields hold objects with mal_id and name. This pulls them up to the top so
    the result looks like a CSV row, then shares the same cleaning.
    """
    aired = raw.get("aired") or {}
    broadcast = raw.get("broadcast") or {}
    fields = {
        **raw,
        "aired_from": aired.get("from"),
        "broadcast_day": broadcast.get("day"),
        "broadcast_time": broadcast.get("time"),
    }
    tags = [name for field in TAG_FIELDS for name in _names(raw.get(field))]
    companies = [
        CompanyRef(item["name"], role, item.get("mal_id"))
        for field, role in COMPANY_ROLES.items()
        for item in raw.get(field) or []
    ]
    return _build_record(fields, tags, companies, data_source="api")


def is_excluded(record: dict[str, Any]) -> bool:
    """True for adult titles (content rating "Rx - Hentai"), which never enter the database."""
    rating = record.get("rating") or ""
    return rating.startswith("Rx")


def dedupe_by_mal_id(records: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    """Keep one record per mal_id (the last one seen) and say how many were dropped.

    The July 2025 CSV repeats some anime as identical rows. A database upsert cannot touch
    the same row twice in one statement, so repeats must go before loading.
    """
    by_id: dict[int, dict[str, Any]] = {}
    for record in records:
        by_id[record["mal_id"]] = record
    return list(by_id.values()), len(records) - len(by_id)
