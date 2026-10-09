-- Question 4: per year, how many titles exist in the whole catalog, how many made it into
-- the population, and the population's median and mean score.
SELECT
    a.year,
    COUNT(*) AS titles_in_catalog,
    COUNT(p.mal_id) AS titles_in_population,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY p.score) AS median_score,
    AVG(p.score)::float8 AS mean_score
FROM anime AS a
LEFT JOIN population AS p ON p.mal_id = a.mal_id
WHERE a.year IS NOT NULL
GROUP BY a.year
ORDER BY a.year;
