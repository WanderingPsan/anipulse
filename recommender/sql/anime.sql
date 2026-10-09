-- One row per anime, in mal_id order so every run builds its matrices in the same order.
SELECT
    a.mal_id,
    a.title,
    a.synopsis,
    a.score::float8 AS score,
    a.members
FROM anime AS a
ORDER BY a.mal_id;
