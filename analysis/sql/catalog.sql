-- The catalog file for the API and dashboard: every anime in the database, with its tags
-- and studios as lists. ARRAY(subquery) gives an empty list when a title has none.
SELECT
    a.mal_id,
    a.title,
    a.title_english,
    a.type,
    a.year,
    a.score::float8 AS score,
    a.members,
    ARRAY(
        SELECT g.name
        FROM anime_genres AS ag
        JOIN genres AS g ON g.genre_id = ag.genre_id
        WHERE ag.anime_id = a.mal_id
        ORDER BY g.name
    ) AS genres,
    ARRAY(
        SELECT c.name
        FROM anime_companies AS ac
        JOIN companies AS c ON c.company_id = ac.company_id
        WHERE ac.anime_id = a.mal_id AND ac.role = 'studio'
        ORDER BY c.name
    ) AS studios
FROM anime AS a
ORDER BY a.mal_id;
