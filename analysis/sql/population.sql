-- The analysis population, defined once. Every question file reads from this view.
-- A temporary view lives only as long as the database connection that created it.
--   score IS NOT NULL: only rated titles can tell us anything about score.
--   members >= 1000: a score from a handful of ratings is mostly noise.
--   status: a title that has not aired cannot have earned its score yet.
CREATE OR REPLACE TEMP VIEW population AS
SELECT *
FROM anime
WHERE score IS NOT NULL
  AND members >= 1000
  AND status IS DISTINCT FROM 'Not yet aired';
