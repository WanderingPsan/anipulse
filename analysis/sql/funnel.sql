-- The database half of the data funnel: how many rows survive each population filter, in
-- order. Each count repeats the earlier filters, so the numbers only ever go down.
SELECT
    COUNT(*) AS in_database,
    COUNT(*) FILTER (WHERE score IS NOT NULL) AS has_score,
    COUNT(*) FILTER (WHERE score IS NOT NULL AND members >= 1000) AS enough_members,
    COUNT(*) FILTER (
        WHERE score IS NOT NULL
          AND members >= 1000
          AND status IS DISTINCT FROM 'Not yet aired'
    ) AS has_aired
FROM anime;
