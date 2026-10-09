-- Every tag link the recommender may use. Explicit genres are left out on purpose (SPEC);
-- "Award Winning" is removed in Python, so the rule lives in one place.
SELECT
    ag.anime_id AS mal_id,
    g.name AS tag,
    g.kind
FROM anime_genres AS ag
JOIN genres AS g ON g.genre_id = ag.genre_id
WHERE g.kind IN ('genre', 'theme', 'demographic')
ORDER BY ag.anime_id, g.name;
