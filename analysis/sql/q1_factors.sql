-- Question 1: one row per population anime with its pre-release factors.
-- Outcome fields (members, scored_by, favorites) are deliberately not selected.
WITH studio_counts AS (
    -- Rank studios by how many population titles they made. The window function numbers
    -- them 1, 2, 3, ... in one pass; ties are broken by name so the order never changes.
    SELECT
        ac.company_id,
        c.name,
        ROW_NUMBER() OVER (ORDER BY COUNT(*) DESC, c.name) AS studio_rank
    FROM anime_companies AS ac
    JOIN population AS p ON p.mal_id = ac.anime_id
    JOIN companies AS c ON c.company_id = ac.company_id
    WHERE ac.role = 'studio'
    GROUP BY ac.company_id, c.name
),
main_studio AS (
    -- A few titles have several studios. Keep the one with the best (lowest) rank.
    SELECT DISTINCT ON (ac.anime_id)
        ac.anime_id,
        sc.name,
        sc.studio_rank
    FROM anime_companies AS ac
    JOIN studio_counts AS sc ON sc.company_id = ac.company_id
    WHERE ac.role = 'studio'
    ORDER BY ac.anime_id, sc.studio_rank
),
demographic AS (
    SELECT
        ag.anime_id,
        CASE WHEN COUNT(*) > 1 THEN 'Multiple' ELSE MIN(g.name) END AS demographic
    FROM anime_genres AS ag
    JOIN genres AS g ON g.genre_id = ag.genre_id
    WHERE g.kind = 'demographic'
    GROUP BY ag.anime_id
)
SELECT
    p.mal_id,
    p.score::float8 AS score,
    p.type,
    p.source,
    p.episodes,
    p.duration_min,
    p.rating,
    p.season,
    p.year,
    COALESCE(d.demographic, 'None') AS demographic,
    CASE
        WHEN ms.anime_id IS NULL THEN 'Unknown'
        WHEN ms.studio_rank <= 15 THEN ms.name
        ELSE 'Other'
    END AS studio_group
FROM population AS p
LEFT JOIN main_studio AS ms ON ms.anime_id = p.mal_id
LEFT JOIN demographic AS d ON d.anime_id = p.mal_id
ORDER BY p.mal_id;
