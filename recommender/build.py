"""Build the recommendations file from the database.

    python -m recommender.build

Reads every anime and its tags, scores similarity in chunks, keeps the top 10 per title,
and writes data/processed/recommendations.parquet plus recommender_eval.json (the
evaluation numbers, so documents can quote a file the code wrote).
"""

import json
import logging
import time
from pathlib import Path

import pandas as pd
from sqlalchemy import Engine, text

from db.session import get_engine
from recommender.evaluate import (
    SPOT_CHECK_IDS,
    coverage,
    median_parts,
    spot_checks,
    tag_overlap,
)
from recommender.features import (
    clean_synopses,
    count_placeholders,
    recommendable,
    recommender_tags,
    tag_lists,
    tag_matrix,
    text_matrix,
)
from recommender.similarity import DEFAULT_K, top_k

logger = logging.getLogger(__name__)

SQL_DIR = Path(__file__).parent / "sql"
PROCESSED_DIR = Path("data/processed")
RECS_PATH = PROCESSED_DIR / "recommendations.parquet"
EVAL_PATH = PROCESSED_DIR / "recommender_eval.json"


def read_inputs(engine: Engine) -> tuple[pd.DataFrame, pd.DataFrame]:
    """The anime table and the tag links, as DataFrames."""
    with engine.connect() as conn:
        anime = pd.read_sql(text((SQL_DIR / "anime.sql").read_text(encoding="utf-8")), conn)
        tags = pd.read_sql(text((SQL_DIR / "tags.sql").read_text(encoding="utf-8")), conn)
    return anime, tags


def build(anime: pd.DataFrame, tags: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Compute recommendations and their evaluation. No file or database access here."""
    started = time.perf_counter()
    ids = anime["mal_id"].to_numpy()
    titles = anime["title"].tolist()
    synopses = clean_synopses(anime["synopsis"].tolist())
    logger.info(
        "Placeholder synopses treated as missing: %d",
        count_placeholders(anime["synopsis"].tolist()),
    )
    tags = recommender_tags(tags)
    eligible = recommendable(anime["score"], anime["members"])

    text_vectors = text_matrix(synopses)
    tag_vectors = tag_matrix(tag_lists(ids.tolist(), tags))
    recs = top_k(ids, text_vectors, tag_vectors, eligible, titles, k=DEFAULT_K)
    runtime = time.perf_counter() - started

    names = dict(zip(ids.tolist(), titles, strict=True))
    spot_rows = [i for i, mal_id in enumerate(ids) if mal_id in SPOT_CHECK_IDS]
    before = top_k(
        ids,
        text_vectors,
        tag_vectors,
        eligible,
        titles,
        query_rows=spot_rows,
        skip_franchise=False,
    )
    genres = tags[tags["kind"] == "genre"]
    # Titles with no recommendations at all count as 0, not as missing.
    per_title = recs.groupby("anime_id").size().reindex(ids, fill_value=0)
    evaluation = {
        "titles": len(ids),
        "recommendable_titles": int(eligible.sum()),
        "titles_without_synopsis": sum(1 for s in synopses if not s),
        "placeholder_synopses": count_placeholders(anime["synopsis"].tolist()),
        "text_features": text_vectors.shape[1],
        "tag_features": tag_vectors.shape[1],
        "recommendation_rows": len(recs),
        "titles_with_fewer_than_k": int((per_title < DEFAULT_K).sum()),
        "tag_overlap_at_10": round(tag_overlap(recs, genres), 4),
        "coverage_of_recommendable": round(coverage(recs, int(eligible.sum())), 4),
        "coverage_of_all_titles": round(coverage(recs, len(ids)), 4),
        "build_runtime_seconds": round(runtime, 1),
        **median_parts(recs, ids, text_vectors, tag_vectors),
        "spot_checks": spot_checks(recs, names, SPOT_CHECK_IDS),
        "spot_checks_without_franchise_rule": spot_checks(before, names, SPOT_CHECK_IDS),
    }
    return recs, evaluation


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    anime, tags = read_inputs(get_engine())
    recs, evaluation = build(anime, tags)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    recs.to_parquet(RECS_PATH, index=False)
    EVAL_PATH.write_text(json.dumps(evaluation, indent=2, ensure_ascii=False) + "\n", "utf-8")
    print(f"Wrote {RECS_PATH} ({len(recs):,} rows)")
    print(f"Wrote {EVAL_PATH}")
    for key in ["tag_overlap_at_10", "coverage_of_recommendable", "build_runtime_seconds"]:
        print(f"{key}: {evaluation[key]}")


if __name__ == "__main__":
    main()
