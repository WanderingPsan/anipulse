"""The AniPulse API.

    python -m uvicorn api.main:app --reload

Then open http://127.0.0.1:8000/docs. The data files are read once at startup, so every
request is a fast in-memory lookup.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware

from api.data import (
    ATTRIBUTION,
    Store,
    data_dir,
    find_anime,
    load_store,
    recommend,
    search,
)
from api.schemas import Anime, Health, RecommendResponse, SearchResponse

DESCRIPTION = f"""
Look up anime and get "if you liked X, try these" recommendations.

Data is served from prebuilt files that are refreshed weekly, not from a live database.

**Data notice:** {ATTRIBUTION}
"""


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Load the data files before the first request is served."""
    app.state.store = load_store(data_dir())
    yield


app = FastAPI(title="AniPulse API", description=DESCRIPTION, version="1.0.0", lifespan=lifespan)
# Any website (like the dashboard) may call the API from a browser, but only to read.
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET"])


def store_of(request: Request) -> Store:
    return request.app.state.store


def anime_or_404(store: Store, mal_id: int) -> dict:
    anime = find_anime(store.catalog, mal_id)
    if anime is None:
        raise HTTPException(status_code=404, detail=f"No anime with mal_id {mal_id}")
    return anime


@app.get("/health", response_model=Health, summary="Is the API up, and how fresh is the data")
def health(request: Request) -> dict:
    store = store_of(request)
    return {
        "status": "ok",
        "last_updated": store.metadata.get("data_last_updated"),
        "anime_count": len(store.catalog),
        "attribution": ATTRIBUTION,
    }


# Declared before /anime/{mal_id} so "search" is not read as a mal_id.
@app.get(
    "/anime/search",
    response_model=SearchResponse,
    summary="Search anime by title",
    description=(
        "Case-insensitive match anywhere in the default title or the English title. "
        "Results are ordered by members, most first."
    ),
)
def search_anime(
    request: Request,
    q: str = Query(min_length=1, description='Text to look for, e.g. "frieren".'),
    limit: int = Query(10, ge=1, le=50, description="Maximum number of results."),
) -> dict:
    results = search(store_of(request).catalog, q, limit)
    return {"query": q, "count": len(results), "results": results}


@app.get(
    "/anime/{mal_id}",
    response_model=Anime,
    summary="One anime by MyAnimeList ID",
    description="Returns 404 if the mal_id is not in the catalog.",
)
def get_anime(request: Request, mal_id: int) -> dict:
    return anime_or_404(store_of(request), mal_id)


@app.get(
    "/recommend/{mal_id}",
    response_model=RecommendResponse,
    summary="Recommendations for one anime",
    description=(
        "Up to k similar titles, best first. A few titles have fewer than 10, or none, and "
        "get however many exist. Returns 404 if the mal_id is not in the catalog. "
        "match_score is a 0 to 1 rank within this title's list; do not compare it across "
        "titles."
    ),
)
def get_recommendations(
    request: Request,
    mal_id: int,
    k: int = Query(10, ge=1, le=10, description="How many recommendations, 1 to 10."),
) -> dict:
    store = store_of(request)
    anime = anime_or_404(store, mal_id)
    recs = recommend(store, mal_id, k)
    return {
        "anime_id": mal_id,
        "title": anime["title"],
        "count": len(recs),
        "recommendations": recs,
    }
