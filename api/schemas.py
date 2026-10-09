"""Response shapes. FastAPI checks every response against these and shows them in /docs."""

from pydantic import BaseModel, Field


class Health(BaseModel):
    status: str = Field(description='"ok" when the data files are loaded.')
    last_updated: str | None = Field(
        description="When the database behind the files was last loaded."
    )
    anime_count: int = Field(description="Number of anime in the catalog.")
    attribution: str = Field(description="Data license notice. Show it wherever the data is shown.")


class AnimeSummary(BaseModel):
    mal_id: int = Field(description="MyAnimeList ID. Frieren is 52991.")
    title: str
    title_english: str | None
    type: str | None = Field(description="TV, Movie, OVA, ONA, Special, ...")
    year: int | None
    score: float | None = Field(description="MyAnimeList score, 1 to 10.")
    members: int | None = Field(description="MyAnimeList users who added the title to a list.")


class Anime(AnimeSummary):
    genres: list[str] = Field(description="Genres, themes, and demographics.")
    studios: list[str]


class SearchResponse(BaseModel):
    query: str
    count: int = Field(description="Number of results returned (at most limit).")
    results: list[AnimeSummary]


class Recommendation(AnimeSummary):
    rank: int = Field(description="1 is the best match.")
    match_score: float = Field(
        description=(
            "A 0 to 1 rank within this title's own list of candidates (1 = best). "
            "It is relative to the title you asked about, so do not compare it across titles."
        )
    )


class RecommendResponse(BaseModel):
    anime_id: int
    title: str
    count: int = Field(description="Number returned. Can be below k, or 0, for some titles.")
    recommendations: list[Recommendation]
