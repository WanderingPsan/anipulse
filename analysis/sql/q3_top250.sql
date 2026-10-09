-- Question 3: the top 250 population titles by score. RANK() gives tied scores the same
-- rank, so a tie at the cutoff can make this list slightly longer than 250.
WITH ranked AS (
    SELECT
        mal_id,
        score,
        RANK() OVER (ORDER BY score DESC) AS score_rank
    FROM population
)
SELECT
    mal_id,
    score::float8 AS score,
    score_rank
FROM ranked
WHERE score_rank <= 250
ORDER BY score_rank, mal_id;
