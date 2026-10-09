"""The franchise heuristic: spot sequels by their titles so they do not crowd out new shows.

A heuristic is a rule of thumb, not a guarantee. It catches "Sousou no Frieren 2nd Season"
for Frieren, but it cannot catch a sequel with a completely different title.
"""

import re

# Small words that start many unrelated titles. Without this list, "Boku no Hero Academia"
# and "Boku no Kokoro no Yabai Yatsu" would both start with "boku no" and look like one series.
FILLER_WORDS = frozenset({"no", "wa", "ga", "wo", "ni", "de", "to", "the", "a", "an", "of"})
KEY_WORDS = 2


def title_words(title: str) -> list[str]:
    """Lowercase words of a title, with punctuation removed and filler words dropped."""
    words = re.sub(r"[\W_]+", " ", title.lower()).split()
    return [word for word in words if word not in FILLER_WORDS]


def franchise_key(title: str) -> str:
    """The first two meaningful words, e.g. "Shingeki no Kyojin Season 2" -> "shingeki kyojin"."""
    return " ".join(title_words(title)[:KEY_WORDS])


def same_franchise(query_title: str, other_title: str) -> bool:
    """True when the other title starts with the query's key words.

    With a one-word key ("Monster"), any title starting with "monster" counts. An empty key
    (a title made only of filler words) never matches, so it cannot hide everything.
    """
    query = title_words(query_title)[:KEY_WORDS]
    if not query:
        return False
    return title_words(other_title)[: len(query)] == query
