-- Question 2: score and members for every population anime. NTILE(10) splits the titles
-- into ten equal-sized groups by members (decile 1 = least popular), for the chart.
SELECT
    mal_id,
    score::float8 AS score,
    members,
    NTILE(10) OVER (ORDER BY members, mal_id) AS members_decile
FROM population
ORDER BY mal_id;
