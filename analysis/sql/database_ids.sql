-- Every anime in the database and where its current values came from. The funnel compares
-- these IDs with the CSV's to count the titles the live API added.
SELECT mal_id, data_source
FROM anime
ORDER BY mal_id;
