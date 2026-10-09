-- Question 1: the genre and theme tags of every population anime, one row per link.
-- Python turns this long list into one yes/no column per common tag.
SELECT
    ag.anime_id AS mal_id,
    g.name AS tag,
    g.kind
FROM anime_genres AS ag
JOIN genres AS g ON g.genre_id = ag.genre_id
JOIN population AS p ON p.mal_id = ag.anime_id
WHERE g.kind IN ('genre', 'theme')
ORDER BY ag.anime_id, g.name;
