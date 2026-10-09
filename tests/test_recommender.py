"""Recommender tests on a tiny made-up catalog. No database: the build logic is pure."""

import numpy as np
import pandas as pd
import pytest

from recommender.build import build
from recommender.evaluate import coverage, median_parts, tag_overlap
from recommender.features import (
    clean_synopses,
    is_placeholder,
    recommender_tags,
    tag_lists,
    tag_matrix,
    text_matrix,
)
from recommender.franchise import franchise_key, same_franchise
from recommender.similarity import (
    TAG_WEIGHT,
    best_k,
    one_per_franchise,
    rank_rescale,
    top_k,
)

ELF = "An elf mage travels with her friends after the demon king is defeated, remembering"
TITAN = "Giant titans attack the walled city and soldiers fight back to save humanity"


def tiny_catalog() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Eight titles: two franchises, an unrelated show, a title with no synopsis, and an
    unscored title that can be looked up but never recommended."""
    anime = pd.DataFrame(
        {
            "mal_id": [1, 2, 3, 4, 5, 6, 7, 8],
            "title": [
                "Sousou no Frieren",
                "Sousou no Frieren 2nd Season",
                "Shingeki no Kyojin",
                "Shingeki no Kyojin Season 2",
                "Elf Journey",
                "Titan Wars",
                "Mage Diary",
                "Unscored Elf",
            ],
            "synopsis": [
                f"{ELF} the past.",
                f"{ELF} the past again.",
                f"{TITAN} today.",
                f"{TITAN} again.",
                f"{ELF} old journeys.",
                f"{TITAN} with friends.",
                None,
                f"{ELF} old journeys.",
            ],
            "score": [9.3, 9.0, 8.5, 8.6, 7.0, 7.1, 6.5, None],
            "members": [1_000_000, 500_000, 4_000_000, 2_000_000, 5_000, 6_000, 2_000, 9_000],
        }
    )
    links = [
        (1, "Adventure", "genre"),
        (1, "Fantasy", "genre"),
        (2, "Adventure", "genre"),
        (2, "Fantasy", "genre"),
        (3, "Action", "genre"),
        (4, "Action", "genre"),
        (5, "Adventure", "genre"),
        (5, "Fantasy", "genre"),
        (6, "Action", "genre"),
        (7, "Fantasy", "genre"),
        (8, "Fantasy", "genre"),
        (1, "Award Winning", "genre"),
        (3, "Award Winning", "genre"),
        (6, "Gore", "explicit_genre"),
    ]
    return anime, pd.DataFrame(links, columns=["mal_id", "tag", "kind"])


@pytest.fixture(scope="module")
def built() -> tuple[pd.DataFrame, dict]:
    return build(*tiny_catalog())


def test_never_recommends_itself(built):
    recs, _ = built
    assert (recs["anime_id"] != recs["similar_id"]).all()


def test_k_is_respected():
    anime, tags = tiny_catalog()
    tags = recommender_tags(tags)
    ids = anime["mal_id"].to_numpy()
    text = text_matrix(clean_synopses(anime["synopsis"].tolist()))
    tag_vectors = tag_matrix(tag_lists(ids.tolist(), tags))
    eligible = np.ones(len(ids), dtype=bool)
    recs = top_k(ids, text, tag_vectors, eligible, anime["title"].tolist(), k=2, chunk_size=3)
    assert recs.groupby("anime_id").size().max() == 2
    assert recs["rank"].between(1, 2).all()


def test_output_is_deterministic():
    first, _ = build(*tiny_catalog())
    second, _ = build(*tiny_catalog())
    pd.testing.assert_frame_equal(first, second)


def test_franchise_sequel_is_skipped_but_other_show_kept(built):
    recs, _ = built
    frieren = recs[recs["anime_id"] == 1]["similar_id"].tolist()
    assert 2 not in frieren
    assert frieren[0] == 5  # Elf Journey, the most similar non-Frieren title


def test_franchise_rule_off_lets_the_sequel_back_in():
    anime, tags = tiny_catalog()
    tags = recommender_tags(tags)
    ids = anime["mal_id"].to_numpy()
    text = text_matrix(clean_synopses(anime["synopsis"].tolist()))
    tag_vectors = tag_matrix(tag_lists(ids.tolist(), tags))
    eligible = np.ones(len(ids), dtype=bool)
    recs = top_k(ids, text, tag_vectors, eligible, anime["title"].tolist(), skip_franchise=False)
    assert recs[recs["anime_id"] == 1]["similar_id"].iloc[0] == 2


def test_unscored_title_can_be_looked_up_but_never_recommended(built):
    recs, _ = built
    assert 8 in set(recs["anime_id"])
    assert 8 not in set(recs["similar_id"])


def test_missing_synopsis_gets_text_similarity_zero(built):
    recs, _ = built
    # Mage Diary has no synopsis, so it can score at most the tag part, 0.3.
    mage = recs[recs["similar_id"] == 7]
    assert not mage.empty
    assert (mage["similarity"] <= TAG_WEIGHT + 1e-6).all()


def test_award_winning_and_explicit_genres_are_dropped():
    _, tags = tiny_catalog()
    kept = recommender_tags(tags)
    assert "Award Winning" not in set(kept["tag"])
    assert "Gore" not in set(kept["tag"])


@pytest.mark.parametrize(
    "synopsis",
    [
        None,
        "   ",
        "No synopsis has been added for this series yet.\n\nClick here to update this information.",
        "No synopsis information has been added to this title.",
    ],
)
def test_placeholder_synopses_count_as_missing(synopsis):
    assert is_placeholder(synopsis)
    assert clean_synopses([synopsis]) == [""]


def test_real_synopsis_is_kept():
    assert not is_placeholder("Frieren outlives her friends and sets out to understand them.")


def test_season_two_shares_the_franchise_key():
    assert franchise_key("Shingeki no Kyojin") == "shingeki kyojin"
    assert same_franchise("Shingeki no Kyojin", "Shingeki no Kyojin Season 2")
    assert same_franchise("Shingeki no Kyojin Season 2", "Shingeki no Kyojin")


def test_unrelated_boku_no_titles_are_not_one_franchise():
    assert franchise_key("Boku no Hero Academia") == "boku hero"
    assert not same_franchise("Boku no Hero Academia", "Boku no Kokoro no Yabai Yatsu")


def test_punctuation_does_not_split_a_franchise():
    assert same_franchise("Steins;Gate", "Steins;Gate 0")


def test_ties_break_toward_the_lower_id():
    scores = np.array([[0.5, 0.9, 0.5, 0.5]], dtype=np.float32)
    _, col = best_k(scores, 2)
    assert col.tolist() == [1, 0]


def test_evaluation_numbers():
    recs = pd.DataFrame({"anime_id": [1, 1, 2], "rank": [1, 2, 1], "similar_id": [2, 3, 1]})
    genres = pd.DataFrame({"mal_id": [1, 2, 3], "tag": ["Drama", "Drama", "Comedy"]})
    assert tag_overlap(recs, genres) == pytest.approx(2 / 3)
    assert coverage(recs, 4) == pytest.approx(3 / 4)


def test_median_parts_uses_both_matrices():
    anime, tags = tiny_catalog()
    ids = anime["mal_id"].to_numpy()
    text = text_matrix(clean_synopses(anime["synopsis"].tolist()))
    tag_vectors = tag_matrix(tag_lists(ids.tolist(), recommender_tags(tags)))
    recs = pd.DataFrame({"anime_id": [1], "rank": [1], "similar_id": [1]})
    assert median_parts(recs, ids, text, tag_vectors) == {
        "median_text_cosine": 1.0,
        "median_tag_cosine": 1.0,
    }


def test_rank_rescale_gives_percentiles_among_allowed_candidates():
    # The 99 is masked, so it neither counts nor gets a score. The two 0.5s tie.
    scores = np.array([[0.1, 0.5, 0.5, 0.9, 99.0]])
    allowed = np.array([[True, True, True, True, False]])
    assert rank_rescale(scores, allowed).tolist() == [[0.0, 0.5, 0.5, 1.0, 0.0]]


def test_rank_rescale_turns_an_all_equal_row_into_zeros():
    scores = np.array([[0.3, 0.3, 0.3]])
    allowed = np.ones((1, 3), dtype=bool)
    assert rank_rescale(scores, allowed).tolist() == [[0.0, 0.0, 0.0]]


def test_one_per_franchise_keeps_the_better_title_and_fills_from_below():
    row = np.array([0, 0, 0, 0])
    col = np.array([0, 1, 2, 3])
    keys = np.array([7, 7, 8, 9])  # columns 0 and 1 are one franchise
    _, kept = one_per_franchise(row, col, keys, k=2)
    assert kept.tolist() == [0, 2]


def test_a_list_holds_one_title_per_franchise():
    anime, tags = tiny_catalog()
    tags = recommender_tags(tags)
    ids = anime["mal_id"].to_numpy()
    text = text_matrix(clean_synopses(anime["synopsis"].tolist()))
    tag_vectors = tag_matrix(tag_lists(ids.tolist(), tags))
    eligible = np.ones(len(ids), dtype=bool)
    titles = anime["title"].tolist()
    titan_wars = [5]
    plain = top_k(
        ids, text, tag_vectors, eligible, titles, k=2, query_rows=titan_wars, skip_franchise=False
    )
    assert set(plain["similar_id"]) == {3, 4}  # both Shingeki no Kyojin titles
    deduped = top_k(ids, text, tag_vectors, eligible, titles, k=2, query_rows=titan_wars)
    assert len(deduped) == 2
    assert len(set(deduped["similar_id"]) & {3, 4}) == 1
