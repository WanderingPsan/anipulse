"""The database tables, written as SQLAlchemy 2.x ORM classes.

Each class is one table. Reading this file top to bottom gives the whole schema: one row per
anime, two lookup tables (genres, companies), two join tables that link them to anime, and a
log of pipeline runs.
"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Identity, Numeric, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Every table class inherits from this, so `Base.metadata` knows all of them."""


class Anime(Base):
    """One row per anime. mal_id is MyAnimeList's ID, so it never changes for a show."""

    __tablename__ = "anime"
    __table_args__ = (
        CheckConstraint(
            "season IN ('winter', 'spring', 'summer', 'fall')", name="anime_season_valid"
        ),
        CheckConstraint("data_source IN ('kaggle', 'api')", name="anime_data_source_valid"),
    )

    mal_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    title: Mapped[str] = mapped_column(Text)
    title_english: Mapped[str | None] = mapped_column(Text)
    type: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str | None] = mapped_column(Text)
    episodes: Mapped[int | None]
    duration_min: Mapped[int | None]
    rating: Mapped[str | None] = mapped_column(Text)
    synopsis: Mapped[str | None] = mapped_column(Text)
    season: Mapped[str | None] = mapped_column(Text)
    year: Mapped[int | None]
    broadcast_day: Mapped[str | None] = mapped_column(Text)
    broadcast_time: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str | None] = mapped_column(Text)
    # numeric(4,2) stores 9.30 exactly. A float could store it as 9.2999999.
    score: Mapped[Decimal | None] = mapped_column(Numeric(4, 2))
    scored_by: Mapped[int | None]
    members: Mapped[int | None]
    favorites: Mapped[int | None]
    data_source: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Genre(Base):
    """Every genre-like tag: genres, explicit genres, themes, and demographics.

    MyAnimeList gives all four one shared ID space (Adventure is 2, Shounen is 27), so one
    table holds them all and `kind` says which family a tag belongs to.
    """

    __tablename__ = "genres"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('genre', 'explicit_genre', 'theme', 'demographic')",
            name="genres_kind_valid",
        ),
    )

    genre_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    name: Mapped[str] = mapped_column(Text, unique=True)
    kind: Mapped[str] = mapped_column(Text)


class AnimeGenre(Base):
    """Links an anime to one of its tags. Frieren has one row here per tag."""

    __tablename__ = "anime_genres"

    anime_id: Mapped[int] = mapped_column(ForeignKey("anime.mal_id"), primary_key=True)
    genre_id: Mapped[int] = mapped_column(ForeignKey("genres.genre_id"), primary_key=True)


class Company(Base):
    """Studios, producers, and licensors. They are one kind of thing on MyAnimeList.

    company_id is our own number because the CSV only gives names. mal_id is filled in
    when the live API tells us the company's MyAnimeList ID.
    """

    __tablename__ = "companies"

    company_id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    mal_id: Mapped[int | None] = mapped_column(unique=True)
    name: Mapped[str] = mapped_column(Text, unique=True)


class AnimeCompany(Base):
    """Links an anime to a company in one role. The role depends on the show, so it lives here."""

    __tablename__ = "anime_companies"
    __table_args__ = (
        CheckConstraint(
            "role IN ('studio', 'producer', 'licensor')", name="anime_companies_role_valid"
        ),
    )

    anime_id: Mapped[int] = mapped_column(ForeignKey("anime.mal_id"), primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.company_id"), primary_key=True)
    role: Mapped[str] = mapped_column(Text, primary_key=True)


class PipelineRun(Base):
    """One row per pipeline run, so we can see when data was loaded and what went wrong."""

    __tablename__ = "pipeline_runs"

    run_id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    # timezone=True makes these timestamptz, so a run logged in UTC reads correctly anywhere.
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    base_source: Mapped[str] = mapped_column(Text)
    api_pages_requested: Mapped[int]
    api_pages_failed: Mapped[int | None]
    anime_upserted: Mapped[int | None]
    status: Mapped[str] = mapped_column(Text)
    message: Mapped[str | None] = mapped_column(Text)
