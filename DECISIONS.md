# Decisions

One entry per meaningful decision: what was chosen, why, and what it costs.

## D-001: The project question
- Component: 0
- Decision: The analysis answers one question: which factors known before an anime airs are
  associated with a higher MyAnimeList score?
- Why: A single, specific question keeps the pipeline, analysis, and dashboard focused. "Before
  it airs" means the answer is useful to someone deciding what to watch or produce, not just a
  description of what already happened.
- Alternatives considered: General "explore the anime data" dashboards (no clear finding), or
  predicting popularity (members), which depends heavily on marketing and timing.
- Trade-off: Fields that only exist after airing (members, favorites, rank) cannot be used to
  explain the score, so some strong correlations are deliberately left out.
- Interview one-liner: "I picked one question I could answer honestly: what you can know before
  a show airs that goes along with a higher score."

## D-002: mal_id is the primary key, not the title
- Component: 0
- Decision: Every anime is identified by its MyAnimeList ID (`mal_id`), never by its title.
- Why: One show has many titles. Frieren (mal_id 52991) has 5 in the API (Default, Japanese,
  English, and synonyms). Different shows also share a title: Hunter x Hunter (1999) and Hunter x
  Hunter (2011) are two separate anime.
- Alternatives considered: Using the title as the key, which would merge different shows and
  split one show into several rows.
- Trade-off: Joining with sources that only have titles needs an extra lookup step.
- Interview one-liner: "Titles aren't unique and aren't stable, so I keyed everything on
  MyAnimeList's own ID."

## D-003: Multi-valued fields use lookup and join tables
- Component: 0
- Decision: Fields that can hold several values per anime (genres, studios, and so on) are
  stored in a lookup table plus a join table.
- Why: Frieren has four genres: Adventure, Award Winning, Drama, and Fantasy. A join table
  stores that as four rows, each holding one value, so "all Drama anime" is a simple, indexed query.
- Alternatives considered: One column per genre (75+ columns that grow whenever MyAnimeList adds
  a genre, and finding one anime's genres means checking every column). "Adventure, Drama" in
  one cell (breaks one value per cell and forces text searching).
- Trade-off: Reading one anime with all its genres needs a join.
- Interview one-liner: "Many-to-many data gets a join table, so every cell holds one value and
  new genres don't change the schema."

## D-004: Lookup tables store each name once, keyed by ID
- Component: 0
- Decision: Each genre or company name is stored once in a lookup table with an ID, and other
  tables refer to that ID.
- Why: The name "Adventure" lives in one row. If MyAnimeList renames it, one row changes.
- Alternatives considered: A hardcoded dict in code (breaks when a new genre appears). Calling
  the API to translate IDs (limited to 60 requests per minute, and the dashboard would break
  during API outages).
- Trade-off: One more table to keep in sync when loading data.
- Interview one-liner: "Names live in one place in the database, so they can't drift and nothing
  depends on the API being up."

## D-005: Shape comes from the JSON brackets
- Component: 0
- Decision: In the API's JSON, a list `[ ]` becomes a join table, even if it is empty or has one
  item for a given anime. An object `{ }` that appears once per anime is flattened into columns.
- Why: The brackets say what the data can hold. Frieren has one studio (Madhouse), but `studios`
  is a list, so other anime can have two. The rule is mechanical, so the schema is consistent.
- Alternatives considered: Deciding per field based on what the data usually looks like, which
  breaks the first time a show has two studios.
- Trade-off: Some join tables hold mostly one row per anime.
- Interview one-liner: "I let the API's own structure decide: lists become join tables, objects
  become columns."

## D-006: broadcast is flattened into broadcast_day and broadcast_time
- Component: 0
- Decision: The `broadcast` object becomes two columns: `broadcast_day` (for example "Fridays")
  and `broadcast_time` ("HH:MM", Japan time).
- Why: Each column holds one value, so "shows that air on Fridays" is a plain filter.
- Alternatives considered: Storing "Fridays at 23:00 (JST)" as one string, which cannot be
  filtered without parsing text in every query.
- Trade-off: The original display string is not stored, and is rebuilt when needed.
- Interview one-liner: "A one-per-anime object gets flattened into columns, so you can filter on
  the day or the time directly."

## D-007: Only pre-release fields are predictors
- Component: 0
- Decision: score, scored_by, members, favorites, rank, and popularity are treated as outcomes.
  They are never used to explain score.
- Why: They are only known after a show airs. Rank is calculated from score, so using rank to
  explain score would be circular.
- Alternatives considered: Using every column, which would produce "findings" like "higher
  ranked shows score higher."
- Trade-off: The model explains less of the variation in score than one that uses outcome
  columns, but its findings are honest.
- Interview one-liner: "I only used what you can know before a show airs, because rank and
  member counts are consequences of the score, not causes."

## D-008: The Kaggle snapshot is the backbone, Jikan is the refresh layer
- Component: 0
- Decision: The full catalog comes from a Kaggle snapshot of MyAnimeList. The Jikan API only
  refreshes and adds recent titles on top of it.
- Why: Jikan is unofficial, rate limited, and unreliable. During early testing it returned
  repeated 504 errors for page 2 of `/top/anime`. A pipeline that depends on it would fail often.
- Alternatives considered: Fetching the whole catalog from Jikan (28,000+ titles at 60 requests
  per minute, with frequent failures).
- Trade-off: Data that Jikan does not refresh is as old as the snapshot (July 2025).
- Interview one-liner: "The pipeline loads a stable snapshot first and treats the live API as an
  optional refresh, so an API outage never breaks a build."

## D-009: The Jikan client throttles and retries with exponential backoff
- Component: 0
- Decision: Every Jikan request waits 0.5 s afterwards. A failed request is retried after 1 s,
  then 2 s, and the error is raised after 3 attempts.
- Why: The throttle keeps us under Jikan's limits (3 requests per second, 60 per minute). Short
  outages often clear within seconds, and doubling the wait avoids hammering a struggling server.
- Alternatives considered: No retries (one 504 kills a run). Infinite retries (a long outage
  hangs the pipeline forever).
- Trade-off: Fetching is slower, and a long outage still fails the request (by design).
- Interview one-liner: "I throttle to stay inside the rate limit, retry with backoff for brief
  outages, and fail loudly after three tries so problems are visible."

## D-010: Dataset is Anime Database (July 2025), under ODbL v1.0
- Component: 0
- Decision: The base dataset is "Anime Database (July 2025)" by sazzadsiddiquelikhon on Kaggle,
  licensed ODbL v1.0. Derived data files are shared under ODbL, every chart or page that shows
  the data carries an attribution notice, and the code stays MIT.
- Why: It is the most recent MyAnimeList snapshot available, and its column names match the
  Jikan API's field names, so one set of cleaning functions can handle both sources.
- Alternatives considered: The 2020 and 2023 Kaggle anime datasets, which are older and use
  different column names.
- Trade-off: ODbL is share-alike, so the processed data files must stay under ODbL.
- Interview one-liner: "I chose the newest snapshot whose columns match the API, and kept the
  data license separate from the code license."

## D-011: The Jikan throttle is 1.0 s, not 0.5 s
- Component: 1
- Decision: Every successful Jikan request is followed by a 1.0 s pause. This replaces the 0.5 s
  pause from D-009.
- Why: Jikan has two limits: 3 requests per second and 60 per minute. A 0.5 s pause allows
  2 per second, which passes the first limit, but over a full minute that is 120 requests,
  double the second limit. A 1.0 s pause allows at most 60 per minute.
- Alternatives considered: Keeping 0.5 s and counting requests per minute (more code to get
  wrong). A token-bucket rate limiter (overkill for one single-threaded script).
- Trade-off: Long fetches take twice as long. 100 pages takes about 2 minutes instead of 1.
- Interview one-liner: "There were two rate limits, and the per-minute one was the tighter one
  for long runs, so I sized the pause for that."

## D-012: Retry only errors that can go away on their own
- Component: 1
- Decision: The client retries connection errors, timeouts, HTTP 429, and HTTP 5xx. Any other
  4xx error (like 404) is raised on the first attempt.
- Why: A 504 means the server was busy, so asking again a second later can work. A 404 means
  the thing does not exist. Asking for `/anime/999999999` three times gives three 404s and
  wastes 3 seconds and 2 requests of our rate limit.
- Alternatives considered: Retrying every error (the Day 1 version), which wastes time and
  requests on errors that can never succeed.
- Trade-off: If Jikan ever sent a 4xx for a temporary problem, we would not retry it.
- Interview one-liner: "I only retry errors that are temporary by nature. A 404 will never
  succeed, so retrying it just burns rate limit."

## D-013: On 429, wait as long as the Retry-After header says (up to 60 s)
- Component: 1
- Decision: When Jikan answers 429 (too many requests) with a `Retry-After: N` header, the
  client waits N seconds before retrying. N is capped at 60. Without the header it uses the
  normal 1 s, 2 s backoff.
- Why: The server knows when it will accept us again. Our own guess of 1 s could be too short,
  which would just earn another 429. The cap means one strange header cannot freeze a run.
- Alternatives considered: Ignoring the header (we would retry too early). No cap (a header
  of 3600 would hang the pipeline for an hour).
- Trade-off: A Retry-After written as a date instead of seconds is ignored and falls back to
  backoff. Jikan sends seconds, so this is rare.
- Interview one-liner: "When the server tells me how long to wait, I listen, with a cap so a
  bad header can't stall the job."

## D-014: Paginated fetches skip a failed page and report it
- Component: 1
- Decision: `get_top_anime(pages)` and `get_season_now(pages)` return a `PageResult` with two
  parts: `items` (every anime from the pages that worked) and `failed_pages` (the page numbers
  that still failed after retries). A failed page is logged, not raised. Paging also stops
  early when Jikan says there is no next page.
- Why: If page 2 of 4 fails, pages 1, 3, and 4 are still good data. Raising would throw them
  away. Returning the failed page numbers keeps the failure visible, and the pipeline can
  store the count in `pipeline_runs.jikan_pages_failed`.
- Alternatives considered: Raising on the first failure (loses good pages). Returning only
  the items (hides failures).
- Trade-off: Callers must check `failed_pages`. A run can "succeed" with fewer anime than
  asked for. The genre reference does the opposite and raises, because a reference file with
  a missing tag family would be silently wrong.
- Interview one-liner: "One bad page shouldn't sink the whole fetch, so I keep what worked and
  report exactly which pages failed."

## D-015: The Kaggle list columns hold names only, not IDs
- Component: 1
- Decision: The list columns in the Kaggle CSV (genres, themes, demographics, studios,
  producers, licensors) are names separated by ", ". For example, Frieren (mal_id 52991) has
  genres `"Adventure, Drama, Fantasy"` and demographics `"Shounen"`. No cell in any of these
  columns contains a number or a bracket. Genre IDs therefore come from the Jikan genre
  reference (`data/reference/jikan_genres.json`), matched by name. `companies.mal_id` stays
  empty for companies that only appear in the CSV.
- Why: This was checked across all 28,858 rows. We also found that `explicit_genres` is empty
  in every row of this snapshot, so the CSV alone cannot tell which titles are Hentai by tag.
  The content rating (`Rx - Hentai`, 1,581 rows) is what we filter on.
- Alternatives considered: Building the genre IDs from the CSV (impossible: there are no IDs).
  Inventing our own genre IDs (would not match Jikan's, so refreshed rows would not line up).
- Trade-off: Matching by name breaks if MyAnimeList renames a tag. That is why the schema
  rules include an alias dict for renamed tags.
- Interview one-liner: "The CSV only had tag names, so I joined them to the API's official
  tag list to get stable IDs instead of making up my own."

## D-016: The Kaggle reader checks the header first and keeps integers as integers
- Component: 1
- Decision: `read_kaggle_csv` reads only the header row first and raises a
  `MissingColumnsError` naming every missing column. Then it loads only the columns in
  `COLUMN_MAP` and stores whole-number columns (episodes, year, members, and others) as pandas'
  nullable `Int64` type. `aired_from` is kept even though the schema has no column for it.
- Why: A renamed column should fail in a fraction of a second with a message like
  "missing required columns: score, genres", not later with a confusing KeyError. With plain
  pandas, one empty cell turns a whole integer column into decimals (Frieren's 28 episodes
  becomes 28.0). `Int64` keeps 28 as 28 and an unknown count as empty. `aired_from` is kept
  because `year` is empty in 22,638 of 28,858 rows, and the air date may be able to fill it.
- Alternatives considered: Loading all 58 columns (slower, and image and trailer URLs are never
  used). Letting pandas guess types (decimals for counts).
- Trade-off: `COLUMN_MAP` is an identity mapping today, so it can look redundant. It is the one
  list of columns we keep and the one place to edit if the source renames a column.
- Interview one-liner: "My reader validates the schema of the file before loading it, so bad
  input fails fast with a message that says exactly what is wrong."

## D-017: The live API is Tenrai, and its base URL is a setting
- Component: 1 (follow-up)
- Decision: The client now calls Tenrai (`https://api.tenrai.org/v1`), a Jikan v4-compatible
  API, instead of Jikan. The module is renamed `ingest/anime_api.py`, the base URL comes from
  the `ANIME_API_BASE_URL` environment variable (default: Tenrai), and the genre reference is
  renamed `data/reference/mal_genres.json`.
- Why: Jikan's public API shut down on 2026-10-01. Tenrai returns the same shapes, so only the
  address had to change. Making the address a setting means the next switch needs no code
  change. The genre IDs belong to MyAnimeList (Adventure is 2 everywhere), so the file is
  named after MyAnimeList, not after the server that delivered it.
- Alternatives considered: Keeping the module name `jikan.py` and only changing the URL
  (misleading for a reader). Hosting our own Jikan server (more work and hosting cost for a
  refresh layer that is optional by design).
- Trade-off: Tenrai does not publish rate limits, so we keep Jikan's (1 request per second),
  which may be slower than needed. Schema and command names that still say "jikan"
  (`data_source = 'jikan'`, `--jikan-pages`) are left unchanged for now.
- Interview one-liner: "When my API shut down, I swapped in a compatible one by changing a
  single environment variable, and my tests kept passing because they never hit the network."

## D-018: Source names are neutral: "api", not "jikan"
- Component: 2
- Decision: The live API's rows are stored with `data_source = 'api'`. The run log columns are
  `pipeline_runs.api_pages_requested` and `api_pages_failed`, and the command flag is
  `--api-pages`. This finishes the rename that D-017 left open.
- Why: The project already switched servers once (Jikan to Tenrai). A database value like
  `'jikan'` would be wrong today, and changing stored values later means a data migration.
  "api" stays true whichever Jikan-compatible server answers.
- Alternatives considered: `'tenrai'` (wrong again after the next switch). Keeping `'jikan'`
  (misleading, since Jikan is shut down).
- Trade-off: "api" says less about where a row came from. The run log and `ANIME_API_BASE_URL`
  carry that detail instead.
- Interview one-liner: "I named the column after the role the source plays, not the vendor,
  so swapping vendors never touches the data."

## D-019: A missing year or season is filled from the air date
- Component: 2
- Decision: When `year` is missing, it becomes the year of `aired_from`. When `season` is
  missing, it comes from the month of `aired_from`: January to March is winter, April to June
  spring, July to September summer, October to December fall. When the source has a year or
  season, it is kept as is.
- Why: In the CSV, `year` and `season` are empty in 22,638 of 28,858 rows, mostly movies,
  OVAs, and specials, which MyAnimeList does not put in a season. Year and season are
  pre-release factors the analysis needs. After filling, 870 of the 27,054 loaded anime have
  no year or season, because they have no air date either. For example, Spirited Away
  (mal_id 199) has no season in the CSV but aired on 2001-07-20, so it becomes summer 2001.
- Alternatives considered: Leaving them empty (the analysis would lose most movies and OVAs).
  Overwriting the source's season with the month rule everywhere (it disagrees with
  MyAnimeList for shows that start at a season's edge: Frieren started on September 29, 2023,
  which the month rule calls summer, but MyAnimeList lists it as fall 2023).
- Trade-off: A filled season is our estimate, not MyAnimeList's label. The two can differ by
  one season near the edges, and the database does not mark which rows were filled.
- Interview one-liner: "Most rows had no season, so I derived it from the air date with a
  documented rule, and only where the source was empty."

## D-020: Two lookup tables instead of seven
- Component: 2
- Decision: The seven list fields (genres, explicit_genres, themes, demographics, studios,
  producers, licensors) share two lookup tables: `genres` and `companies`.
- Why: MyAnimeList gives genres, explicit genres, themes, and demographics one ID space
  (Adventure is 2, Shounen is 27, all under `/anime/genre/`). Studios, producers, and
  licensors are one kind of entity too: Madhouse is company 11 whether it is credited as a
  studio or a producer. Seven tables would store Madhouse twice and split one ID space in four.
- Alternatives considered: One lookup and one join table per field (14 tables, duplicated
  names, and a query for "all of Frieren's tags" would need four joins).
- Trade-off: Each table needs an extra column (`kind` or `role`) to say which family a row is
  in.
- Interview one-liner: "I modeled the entities the source actually has, so one company is one
  row no matter how many roles it plays."

## D-021: `kind` lives on `genres`, but `role` lives on the join table
- Component: 2
- Decision: A tag's family (`kind`) is a column of `genres`. A company's job (`role`) is a
  column of `anime_companies`, and it is part of that table's primary key.
- Why: A tag's kind never changes: Shounen is always a demographic. A company's role depends
  on the show: Aniplex produces one show and licenses another. A fact belongs on the table
  whose key it depends on.
- Alternatives considered: `role` on `companies` (would force one role per company, which is
  false).
- Trade-off: None worth noting. This is what the data's shape requires.
- Interview one-liner: "Kind describes the tag, so it is on the tag. Role describes the tag's
  relationship to one show, so it is on the link."

## D-022: `companies` uses its own ID
- Component: 2
- Decision: `companies.company_id` is a number the database assigns. MyAnimeList's ID is kept
  in a separate `mal_id` column that can be empty.
- Why: The CSV has only company names (D-015). Looking up every company's ID from the API would
  take thousands of rate-limited calls. When the live API mentions a company, its `mal_id` is
  filled in, and a later CSV load never erases it.
- Alternatives considered: Using the name as the key (names are long and can change). Waiting
  for IDs from the API (thousands of calls at 1 per second).
- Trade-off: Two companies are matched by exact name, so a company spelled two ways would get
  two rows.
- Interview one-liner: "The CSV had no company IDs, so I gave them surrogate keys and fill in
  the official ID whenever the API provides it."

## D-023: No Alembic; tables are created with `create_all`
- Component: 2
- Decision: `python -m db.init` creates the tables with SQLAlchemy's `create_all`.
- Why: This is a one-developer project with a fresh schema, and the database can be rebuilt
  from the committed dataset in under a minute (D-024). Migrations solve a problem we do not
  have yet.
- Alternatives considered: Alembic migrations from day one (more files and concepts for no
  current benefit).
- Trade-off: `create_all` never changes a table that already exists. If the schema changes,
  the database must be dropped and rebuilt, or Alembic added then.
- Interview one-liner: "I kept schema management as simple as the project allowed and know
  Alembic is the next step once the schema has to change under live data."

## D-024: No database snapshot is committed
- Component: 2
- Decision: The database is always rebuilt from the committed dataset zip plus a live API
  refresh. No dump of the database is stored.
- Why: The zip is already committed, and a full load takes about 15 seconds. A snapshot would
  be a second copy of the same data that could drift from the code.
- Alternatives considered: Committing a `pg_dump` after each refresh (large binary diffs, and
  a second source of truth).
- Trade-off: API updates from earlier weekly refreshes are not kept, only the latest run's.
  An anime that the API refreshed last week but not this week goes back to its CSV values.
- Interview one-liner: "The database is a build output: anyone can rebuild it from the
  committed source data with one command."

## D-025: Repeated rows in the CSV are dropped before loading
- Component: 2
- Decision: When the same `mal_id` appears more than once, one record is kept and the rest are
  counted as dropped. The run summary prints the count.
- Why: The CSV has 231 `mal_id`s that appear 2 to 4 times, and every copy is identical in every
  column. A Postgres upsert cannot update the same row twice in one statement, so repeats
  would crash the load. After the Rx filter, 224 repeated rows are dropped.
- Alternatives considered: Letting the database reject them (crashes the batch). Removing
  them inside `read_kaggle_csv` (hides the problem from the run summary).
- Trade-off: If a future snapshot repeats a `mal_id` with different values, we keep the last
  one without comparing them.
- Interview one-liner: "I found 231 duplicated IDs in the source, confirmed the copies were
  identical, and drop them in a counted step instead of silently."

## D-026: Company names keep their legal suffix when a cell is split
- Component: 2
- Decision: When splitting a company cell on ", ", a piece that is only a legal suffix
  ("Inc.", "Ltd.", "LLC") is joined back to the name before it.
- Why: Some names contain a comma. "NIS America, Inc." is credited on 55 anime and "Horgos
  Coloroom Pictures Co., Ltd." on 8. A plain split would create a fake company called "Inc."
  credited on dozens of shows. After loading, no company is named just "Inc." or "Ltd.".
- Alternatives considered: A list of every comma-containing company name (breaks on the next
  new company). Ignoring it (creates fake companies).
- Trade-off: A suffix we did not list would still split. The list covers every case in this
  snapshot.
- Interview one-liner: "The list cells used commas both as separators and inside names, so I
  rejoin legal suffixes after splitting."

## D-027: Durations are stored in whole minutes, and never as 0
- Component: 2
- Decision: `parse_duration` adds up hours, minutes, and seconds and rounds to whole minutes.
  Anything shorter than half a minute becomes 1, not 0.
- Why: 734 rows give their length in seconds ("33 sec per ep"). The schema stores whole
  minutes, and 0 would read as "no length", which is wrong.
- Alternatives considered: Storing seconds (changes Toast's schema). Treating seconds-long
  titles as unknown (throws away real data).
- Trade-off: A 33-second episode and a 1-minute episode look the same.
- Interview one-liner: "I parsed every duration format in the data and rounded to the
  schema's unit without letting short clips become zero."

## D-028: Both sources match tags by name, and links are replaced per batch
- Component: 2
- Decision: CSV and API records both list tag names, which are matched to
  `data/reference/mal_genres.json` (with the alias dict for renamed tags). Unmatched names are
  logged and counted. Each batch of 1,000 anime runs in one transaction: upsert the anime,
  upsert their companies, delete their old links, insert the current links.
- Why: One matching path for both sources means one set of tests. Today every tag in the CSV
  matches (0 unmatched). Deleting and reinserting links is simpler than working out which
  links changed, and the transaction means nobody sees an anime with no tags halfway through.
- Alternatives considered: Using the API's tag IDs directly (a second code path, and a new
  tag missing from the reference file would break the foreign key instead of being counted).
- Trade-off: A brand-new MyAnimeList tag is skipped (and reported) until the reference file is
  rebuilt.
- Interview one-liner: "Every load is an upsert plus a delete-and-reinsert of links in one
  transaction, so running it twice changes nothing."

## D-029: The live API is optional to a run; the CSV is not
- Component: 2
- Decision: `pipeline.run` exits with an error only when the base CSV load fails. If API pages
  fail, the run is logged as `partial` with the failed page count, and the CSV data stays.
  The refresh uses the top-anime endpoint, 25 anime per page, loaded after the CSV so the
  newer API values win.
- Why: The API has gone down before (Jikan's 504s, then its shutdown). A weekly refresh that
  fails because of someone else's server should not leave us with no database.
- Alternatives considered: Failing the whole run on any API error (the dashboard would lose
  data for an outage we cannot fix).
- Trade-off: A run can "succeed" with stale data. The `pipeline_runs` table records that so it
  is visible.
- Interview one-liner: "The snapshot is the backbone and the API is a refresh layer, so an API
  outage downgrades a run to partial instead of failing it."

## D-030: Database tests run in a throwaway schema, with CHECK constraints guarding values
- Component: 2
- Decision: Database tests create their tables in a separate schema, `anipulse_test`, and drop
  it afterwards. The tables also have CHECK constraints: `season`, `kind`, `role`, and
  `data_source` only accept their listed values.
- Why: A developer's DATABASE_URL usually points at their real, loaded database. Tests that
  drop or fill tables there would wipe it. The constraints mean a typo like "Fall" or
  "studios" is rejected by the database instead of becoming a silent fourth category.
- Alternatives considered: A separate test database (one more thing to create by hand).
  Validating values only in Python (another program writing to the database could skip it).
- Trade-off: The test schema needs permission to create schemas, which the project's own
  database user has.
- Interview one-liner: "My tests can't touch real data, and the database itself refuses values
  outside the allowed categories."

## D-031: The data funnel starts at the raw CSV and recounts the pipeline's cleaning steps
- Component: 3
- Decision: `analysis.run` reads the committed CSV and runs the pipeline's own Rx filter and
  de-duplication (`is_excluded`, `dedupe_by_mal_id`) to count those steps again. It then
  compares mal_ids with the database to count the titles the live API added, and the SQL
  filters finish the funnel. The steps must add up to the database's row count, or the run
  stops with an error.
- Why: The database only holds the rows that survived cleaning, so it cannot say how many were
  removed. Recounting with the same functions gives the same answer the pipeline got: 28,858
  raw rows, 1,581 Rx titles, 224 duplicate rows, and 1 title added by the API in the run used
  to write FINDINGS.md. Every row is accounted for.
- Alternatives considered: Parsing the counts out of `pipeline_runs.message` (free text, and
  it only describes the last run). New columns on `pipeline_runs` (a schema change, and still
  per-run).
- Trade-off: The analysis reads the CSV as well as the database, which adds a few seconds.
- Interview one-liner: "My funnel accounts for every row from the raw file to the analysis
  population, and it refuses to run if the steps don't add up."

## D-032: The analysis population is defined once, as a temporary view
- Component: 3
- Decision: `analysis/sql/population.sql` creates a temporary view called `population`
  (score not null, at least 1,000 members, not "Not yet aired"). Every question's SQL file
  reads from that view.
- Why: Four questions share one population. If each file repeated the filter, changing the
  members cutoff would mean editing four files and hoping none was missed.
- Alternatives considered: Copying the WHERE clause into each file. A permanent view (a schema
  change, and the database would then depend on the analysis).
- Trade-off: A temporary view only exists on the connection that made it, so all queries run
  on one connection.
- Interview one-liner: "The population rules live in exactly one place, so every question is
  answered about the same set of titles."

## D-033: Results lead with effect sizes on one shared scale
- Component: 3
- Decision: Every test reports an effect size between 0 and 1: rho squared for Spearman and
  epsilon squared (H divided by n minus 1) for Kruskal-Wallis. Both mean "the share of the
  variation in score ranks this factor explains". Tables are sorted by effect size and
  labelled negligible (below 0.01), small (to 0.06), medium (to 0.14), or large.
- Why: With about 12,650 titles, almost any difference is statistically significant. In the
  run behind FINDINGS.md, 33 of 60 tests were significant and 15 of those had a negligible
  effect. A p-value says "probably not zero"; an effect size says "how big".
- Alternatives considered: Ranking by p-value (most are below 0.001, so they cannot be ranked).
  Reporting rho and H as they are (they are on different scales and cannot be compared).
- Trade-off: The cutoffs for the labels are conventions, not laws.
- Interview one-liner: "With twelve thousand titles everything is significant, so I ranked
  factors by how much they explain, not by their p-values."

## D-034: All p-values are adjusted together with Benjamini-Hochberg
- Component: 3
- Decision: Every Spearman and Kruskal-Wallis test in the analysis (questions 1 to 3) goes into
  one Benjamini-Hochberg correction (`statsmodels` `multipletests`, method `fdr_bh`). Tables
  show the raw and adjusted p-value side by side.
- Why: Run 60 tests at p < 0.05 and about 3 come out "significant" by luck. Benjamini-Hochberg
  keeps the expected share of false discoveries among the hits at 5%.
- Alternatives considered: Bonferroni (divides the cutoff by 60, so it misses real effects).
  No correction (overstates the evidence).
- Trade-off: Adjusted p-values are larger, so a few borderline results stop being significant.
- Interview one-liner: "I ran 60 tests, so I corrected for multiple comparisons with
  Benjamini-Hochberg and show both p-values."

## D-035: The "Award Winning" tag is left out of the analysis
- Component: 3
- Decision: The genre "Award Winning" is never one of the tested tags or a model feature.
- Why: MyAnimeList adds it after a show wins an award, so it is an outcome, like score
  (D-007). Frieren has it. Using it would explain good scores with good reception.
- Alternatives considered: Keeping every genre as the spec's "most common genres" wording
  suggests (leaks an outcome into the predictors).
- Trade-off: None for the question asked; the tag is still in the catalog file.
- Interview one-liner: "One genre tag is only given after release, so I treated it as an
  outcome and kept it out of the model."

## D-036: How titles with several, or no, studios and demographics are grouped
- Component: 3
- Decision: Studios are ranked by title count in the population with a window function. A
  title with several studios is grouped under its highest-ranked one. The top 15 keep their
  names, the rest are "Other", and titles with no studio are "Unknown". A title's demographic
  is its one demographic tag, "None" if it has none, or "Multiple" if it has more than one.
  Any other missing category (source, rating, season) is "Unknown".
- Why: Category tests need each title in exactly one group. Most titles have one studio, so
  picking the best-known keeps the most information. "Unknown" is kept as its own group because
  missing data is not random: titles with no studio listed score lower.
- Alternatives considered: Counting a multi-studio title once per studio (counts it twice in
  the same test). Dropping titles with missing values (loses them from every test).
- Trade-off: A co-production is credited to only one of its studios.
- Interview one-liner: "Every title lands in exactly one group per factor, and 'unknown' is a
  group, not a dropped row."

## D-037: The regression model and how it is judged
- Component: 3
- Decision: One OLS model (statsmodels, HC3 robust standard errors) of score on every
  pre-release factor plus the tag indicators. Each category's most common value is the
  reference. Episodes and duration enter as log(1 + x). Rows missing episodes, duration, or
  year are left out (86 in the run behind FINDINGS.md). The model is judged by 5-fold
  cross-validated R squared next to a predict-the-mean baseline.
- Why: The log stops a few 1,000-episode shows from steering the line. HC3 standard errors
  stay honest when some groups' scores are more spread out than others'. Cross-validation
  measures R squared on titles the model did not learn from, which in-sample R squared
  overstates.
- Alternatives considered: A tree model (predicts better but its coefficients cannot be read
  as "compared with the reference"). Filling in missing values (invents data for under 1% of
  rows).
- Trade-off: A straight-line model misses interactions, like a studio being strong only in one
  genre.
- Interview one-liner: "I fit one interpretable model and reported its cross-validated R
  squared against a baseline, so I don't overstate how predictable scores are."

## D-038: The common tags are the top 15 genres and top 10 themes
- Component: 3
- Decision: The tested tags are the 15 most frequent genres and the 10 most frequent themes in
  the population, each as a yes/no factor. Ties in frequency are broken by name.
- Why: Rare tags give tiny groups whose medians jump around. There are fewer common themes
  than genres, so fewer themes are taken.
- Alternatives considered: Every tag (78 tests, many with a handful of titles). A frequency
  cutoff like 5% (the list would change size between data refreshes).
- Trade-off: Rare but distinctive tags are not tested.
- Interview one-liner: "I tested the 25 most common tags as yes/no factors so every group was
  large enough to trust."

## D-039: FINDINGS.md is filled from a template, and reruns give identical files
- Component: 3
- Decision: The text lives in `analysis/FINDINGS_TEMPLATE.md` with `$placeholders`, filled by
  Python's `string.Template.substitute`. The bootstrap uses a fixed random seed (42).
- Why: `substitute` raises an error if any placeholder has no value, so the report can never
  ship with a gap or a hand-typed number. The fixed seed means running the analysis twice on
  the same database writes byte-identical files (only the `generated_at` time changes), so a
  change in the output always means a change in the data or the code.
- Alternatives considered: Jinja2 (a new dependency for something the standard library does).
  Writing the numbers by hand (goes stale after the next refresh).
- Trade-off: Sentences whose wording depends on the result (like "the biggest is medium") need
  small helper functions.
- Interview one-liner: "Every number in my write-up is generated, and the analysis is
  reproducible to the byte."

## D-040: The top 250 keeps ties at the cutoff
- Component: 3
- Decision: The top 250 for question 3 uses `RANK()`, so titles tied with the 250th score are
  all kept. In the run behind FINDINGS.md this gave 253 titles.
- Why: Cutting a tie in half would pick between equal titles by an arbitrary rule.
- Alternatives considered: `ROW_NUMBER()` (exactly 250, but the cut through a tie depends on
  sort order).
- Trade-off: "Top 250" can hold slightly more than 250 titles; FINDINGS.md prints the real count.
- Interview one-liner: "I used RANK instead of ROW_NUMBER so tied scores are treated the same."

## D-041: Recommendations use synopsis words and tags, without explicit genres or "Award Winning"
- Component: 4
- Decision: Each title becomes two vectors: TF-IDF of its synopsis (English stop words,
  one- and two-word phrases, words in at least 2 synopses, at most 30,000 features) and a
  multi-hot list of its genres, themes, and demographics. Explicit genres and the
  "Award Winning" genre are left out.
- Why: The synopsis says what a show is about; tags say what kind of show it is. "Award
  Winning" describes how a show was received, not what it is (same reason as D-035), so two
  shows sharing it are not alike. Frieren and Cowboy Bebop both have it.
- Alternatives considered: Word embeddings from a language model (a new dependency and much
  slower to build); including every tag (rewards fame instead of content).
- Trade-off: TF-IDF matches words, not meaning: "demon king" in two synopses counts as a link
  even if the shows feel nothing alike.
- Interview one-liner: "Content-based means I compare what shows are about, using synopsis
  words and genre tags, and I left out a tag that only reflects reception."

## D-042: One blend formula for every pair, with text similarity 0 when a synopsis is missing
- Component: 4
- Decision: Similarity = 0.7 x text cosine + 0.3 x tag cosine for every pair of titles. When
  either title has no synopsis, its text cosine is 0, so the pair can score at most 0.3.
- Why: Tag cosines run much higher than text cosines. Two shows with the same genres score
  1.0 on tags, but two synopses share only a few words. Among the final recommendations the
  median tag cosine is 0.894 and the median text cosine is 0.046. Ranking some candidates on
  tags alone would push titles without a synopsis above better matches.
- Alternatives considered: Switching to tags only when a synopsis is missing (puts two
  numbers on different scales into one ranking).
- Trade-off: A title with no synopsis is rarely recommended, and its own list is driven by
  tags only, at low similarity values.
- Interview one-liner: "I kept one scoring formula for every pair so all similarities sit on
  the same scale and can be ranked together."
- Update: D-048 keeps this formula but blends percentile ranks instead of raw cosines.

## D-043: Placeholder synopses count as missing
- Component: 4
- Decision: A synopsis that starts with "No synopsis has been added" or "No synopsis
  information has been added" is treated as empty. The build counts them (22 in the current
  database).
- Why: Every placeholder uses the same sentence, so TF-IDF would call all those titles near
  copies of each other and recommend them to one another.
- Alternatives considered: Leaving them in (fake matches); deleting them in the pipeline
  (the text is still what MyAnimeList shows, so the database keeps it as is).
- Trade-off: A new placeholder wording would slip through until it is added to the pattern.
- Interview one-liner: "I found a stock 'no synopsis' sentence in the data and treated it as
  missing, or every placeholder title would have matched every other one."

## D-044: Any title can be looked up, but only scored titles with 1,000+ members are recommended
- Component: 4
- Decision: Every anime gets a recommendation list, but a title can appear in someone's list
  only if it has a score and at least 1,000 members. That is 12,657 of 27,054 titles.
- Why: Suggestions should be shows people have actually watched. A two-minute promotional
  clip with 300 members can have a synopsis close to Frieren's, but nobody would thank us for
  recommending it. Looking up any title still works, so a niche show gets suggestions too.
- Alternatives considered: No filter (obscure titles crowd the lists); filtering the queries
  too (searching for a niche title would return nothing).
- Trade-off: Catalog coverage is measured against the 12,657 recommendable titles; over all
  titles it can never pass 47%.
- Interview one-liner: "Anyone can look up any show, but I only recommend shows with a score
  and at least a thousand members, so suggestions are things people have actually watched."

## D-045: Similarity is computed 1,000 rows at a time, and ties break the same way every run
- Component: 4
- Decision: The build scores 1,000 query titles against all titles with sparse matrix
  products, finds each row's top 10 with `argpartition`, and discards the rest before the
  next chunk. Ties are broken toward the lower mal_id. A pair with similarity 0 is never
  recommended, so a title that shares nothing with anyone gets fewer than 10 rows (27 do).
- Why: The full table would be 27,054 x 27,054 numbers, about 6 GB as 64-bit floats. One chunk
  is about 100 MB. `argpartition` finds the 10 best without sorting all 27,054 scores.
  `argpartition` alone picks an arbitrary title among ties at the cutoff, so every candidate at
  or above the 10th score is sorted by score and then mal_id.
- Alternatives considered: A nearest-neighbor library (a new dependency for a build that
  takes under two minutes); padding short lists with zero-similarity titles (random noise).
- Trade-off: Scores are recomputed from scratch on every build, which takes about 90 seconds.
- Interview one-liner: "I never build the full similarity matrix; I process a thousand rows at
  a time and keep only the top ten per row, which keeps memory around 100 MB instead of 6 GB."
- Update: since D-048 only the 12,657 recommendable titles are scored as candidates, and since
  D-049 the top 50 are kept before repeats of a franchise are dropped.

## D-046: The franchise heuristic skips neighbors that start with the same two meaningful words
- Component: 4
- Decision: A title's key is the first two words of its title after lowercasing, removing
  punctuation, and dropping filler words (no, wa, ga, wo, ni, de, to, the, a, an, of). A
  neighbor whose title starts with the query's key is skipped. A title with a one-word key
  skips neighbors that start with that word. This is a heuristic, not a franchise database.
- Why: Without it, Shingeki no Kyojin's top 5 are all its own seasons and Steins;Gate's top 5
  are all Steins;Gate spin-offs, which a fan already knows about. Filler words matter because
  "Boku no Hero Academia" and "Boku no Kokoro no Yabai Yatsu" both start with "boku no" but
  are unrelated; after dropping "no" their keys are "boku hero" and "boku kokoro".
- Alternatives considered: MyAnimeList's relations data (thousands of extra API calls);
  comparing whole titles (misses "Season 2").
- Trade-off: Sequels with a different title still get through, because the rule only reads
  titles. Two unrelated shows that share their first two key words are wrongly skipped.
- Interview one-liner: "I skip recommendations whose titles start like the query's, after
  dropping particles like 'no', so Season 2 doesn't crowd out new shows."

## D-047: How the recommendations are evaluated
- Component: 4
- Decision: Four checks, written by the build to `data/processed/recommender_eval.json`:
  tag overlap at 10, catalog coverage, build runtime, and spot checks of five well-known titles.
- Why: There are no "correct" recommendations to test against. These proxies catch the common
  failures: suggestions that share no genre with the query, and lists that keep repeating the
  same few shows. Results from the current build:
  - Tag overlap at 10: 93.9% of recommendations share at least one genre with their query
    (counted over queries that have a genre).
  - Catalog coverage: 97.9% of the 12,657 recommendable titles appear in at least one list
    (45.8% of all 27,054 titles, see D-044).
  - Build runtime: 91.2 seconds for 270,270 recommendation rows. Two builds in a row wrote
    identical files.
  - Which half decides: among recommended pairs the median tag cosine is 0.894 and the
    median text cosine is 0.046. The blend gives text 70% of the weight, but most pairs share
    few synopsis words, so tags decide most lists and text breaks the ties between them.
  - Spot checks: Shingeki no Kyojin now recommends Highschool of the Dead and Koutetsujou no
    Kabaneri instead of its own seasons; Steins;Gate's spin-offs give way to Human Lost and
    Re:Zero. Frieren's list is weaker (a Dragon Ball Z special appears), because her tags are
    common and few synopsis words are shared.
- Alternatives considered: Holding out user ratings (we have no per-user data).
- Trade-off: High tag overlap is easy to reach because tags are part of the score, so it is a
  sanity check, not proof of quality.
- Interview one-liner: "Without user data I checked genre overlap, coverage, runtime, and
  read the lists for five famous shows, and I report where the results are weak."
- Update: the numbers above are from the first version. D-048 and D-049 changed the blend and
  the lists; current numbers are in D-049.

## D-048: Text and tag similarity are turned into percentile ranks before blending
- Component: 4
- Decision: For each query, the text cosine and the tag cosine of every allowed candidate
  (recommendable, not itself, not its franchise) are each replaced by a percentile rank from
  0 (worst) to 1 (best). Ties share the average rank. Then similarity = 0.7 x text rank +
  0.3 x tag rank. Text stays 0 when either title has no synopsis. If every allowed score in a
  row is equal, that part is 0 for the row. Pairs that share no word and no tag are still
  never recommended. Only the 12,657 recommendable titles are scored as candidates.
- Why: Raw tag cosines sit near 1 and raw text cosines near 0 (medians 0.894 and 0.046 in
  D-047), so the 70/30 weights did not mean what they said and tags decided most lists.
  Frieren's top 5 included a Dragon Ball Z special. Three versions were built on the same
  database and compared:

  | Metric | Raw blend | Min-max | Percentile rank |
  |---|---|---|---|
  | Tag overlap at 10 | 93.9% | 77.0% | 93.4% |
  | Coverage of recommendable titles | 97.9% | 98.4% | 97.6% |
  | Median text cosine of picks | 0.046 | 0.138 | 0.076 |
  | Median tag cosine of picks | 0.894 | 0.676 | 0.775 |
  | Build runtime (seconds) | 71.2 | 92.2 | 221.4 |

  Min-max (lowest score becomes 0, highest becomes 1) made text decide almost alone, and
  the lists drifted off-genre: Fullmetal Alchemist: Brotherhood got a shop-keeping comedy.
  Percentile rank let text count more while keeping genre overlap. Frieren's top 5 went from
  "Yuusha Party wo Tsuihou sareta Shiromadoushi, Dragon Ball Z Special 2, RG Veda, 100-man no
  Inochi no Ue ni Ore wa Tatteiru, Gensoumaden Saiyuuki" to "Dragon Quest: Dai no Daibouken
  (2020), 100-man no Inochi no Ue ni Ore wa Tatteiru, Dragon Quest: Dai no Daibouken, Yuusha
  Party wo Tsuihou sareta Shiromadoushi, Gensoumaden Saiyuuki". Percentile rank was chosen.
  Ranking only recommendable titles instead of all 27,054 gave the same file and cut the
  build from 221.4 to 92.7 seconds.
- Alternatives considered: Min-max rescaling (above); keeping raw cosines and changing the
  weights (the scales would still differ from query to query).
- Trade-off: The stored similarity is now relative to each query's candidates, not a raw
  cosine. A 0.9 means "near the top of this show's candidates", so values from two different
  queries are not comparable.
- Interview one-liner: "My text and tag scores lived on different scales, so I turned each
  into a percentile rank per query before blending, which made the 70/30 weights real."

## D-049: A list holds at most one title per franchise key
- Component: 4
- Decision: After scoring, each title's top 50 candidates are taken, and any candidate whose
  franchise key (D-046) equals the key of a better-ranked candidate in the same list is
  dropped. The first 10 that remain are kept. Titles with no key words are never grouped.
- Why: The D-046 rule only hides the query's own franchise. Other franchises could still
  take two slots: Frieren's list had two Dragon Quest: Dai no Daibouken entries and Shingeki
  no Kyojin's had two Koutetsujou no Kabaneri entries. Before this rule, 10,128 lists had a
  repeated key (with percentile ranks already in place); after it, none do. Taking 50 candidates first lets lists still reach 10.
- Alternatives considered: Taking only the top 10 and then filtering (lists would shrink).
- Trade-off: Keys must match exactly, so "Saraba Uchuu Senkan Yamato" and "Uchuu Senkan
  Yamato 2202" both stay in Cowboy Bebop's list. Ten more titles end with fewer than 10
  recommendations (37 instead of 27), mostly Lupin and Detective Conan spin-offs whose 50
  best candidates are nearly all one franchise. Current results with D-048 and D-049: tag
  overlap at 10 is 93.2%, coverage of recommendable titles 96.3% (45.0% of all titles),
  median text cosine 0.075 and tag cosine 0.772, 270,228 rows, build runtime 91.2 seconds,
  and two builds in a row wrote identical files. Frieren's top 5 is now Dragon Quest: Dai no
  Daibouken (2020), 100-man no Inochi no Ue ni Ore wa Tatteiru, Yuusha Party wo Tsuihou
  sareta Shiromadoushi, Gensoumaden Saiyuuki, and Mai Mai Shinko to Sennen no Mahou.
- Interview one-liner: "I let each franchise take one slot per list, so five suggestions
  means five different shows."

## D-050: The API reads prebuilt files, not Postgres
- Component: 5
- Decision: At startup the API loads `catalog.parquet`, `recommendations.parquet`, and
  `metadata.json` from `ANIPULSE_DATA_DIR` (default `data/processed`) into memory. It never
  connects to the database.
- Why: Free hosting has no database that stays awake, and these files are rebuilt weekly
  anyway, so a live database would add cost and a failure point without fresher answers. The
  files are small (about 2 MB on disk), and lookups take a few milliseconds: a recommendation
  request for Frieren (52991) took about 3 ms on the full data.
- Alternatives considered: Querying Postgres per request (needs a hosted database); SQLite
  (still a second copy of the data to build and ship).
- Trade-off: Data is only as fresh as the last rebuild, and new files need a restart to load.
  A missing file stops startup with an error naming it, rather than serving empty answers.
- Interview one-liner: "My API serves read-only data that changes weekly, so I load prebuilt
  files into memory and skip the database entirely."

## D-051: The recommender's similarity is exposed as match_score
- Component: 5
- Decision: `/recommend` returns the stored `similarity` column as `match_score`, rounded to 4
  decimals, and `/docs` describes it as a 0 to 1 rank within this title's own list that should
  not be compared across titles.
- Why: Since D-048 the number is a percentile-rank blend relative to each title's candidates,
  not a raw cosine. Calling it "similarity" invites reading 0.99 as "almost identical" and
  comparing it between shows. Frieren's first pick and some other show's first pick can both
  score about 0.99 while being very different matches.
- Alternatives considered: Keeping the name `similarity` (misleading); hiding the number and
  returning only rank (callers lose a way to see how close picks are inside one list).
- Trade-off: The API field name differs from the column name in the file, so readers of both
  need this note.
- Interview one-liner: "The score is a rank inside one show's list, so I named it match_score
  and documented that it isn't comparable across shows."

## D-052: An unknown anime is a 404, a short list is a normal answer
- Component: 5
- Decision: `/anime/{mal_id}` and `/recommend/{mal_id}` return 404 only when the mal_id is not
  in the catalog. A known title gets 200 with however many recommendations exist, up to k,
  with a `count` field. `k` must be 1 to 10, and anything else is rejected with 422.
- Why: 37 titles have fewer than 10 recommendations (D-049): 27 have none and 10 have 3 to 8.
  Those titles exist; they just have few good matches. Returning an error would make the
  dashboard treat a real show as missing. Ten is the most the file holds per title.
- Alternatives considered: 404 when the list is empty (confuses "no such show" with "no
  picks"); padding short lists with weaker matches (the build already decided they are not
  good enough).
- Trade-off: Callers must handle an empty list.
- Interview one-liner: "404 means the show doesn't exist; an empty list means it exists but
  has nothing good to recommend, and those are different answers."

## D-053: Search is a plain-text substring match, ordered by members
- Component: 5
- Decision: `/anime/search` finds titles whose default or English title contains the query,
  ignoring case, and treats the query as plain text (so "(" or "?" are not pattern syntax).
  Results are ordered by members, most first, then by mal_id. `limit` is 1 to 50.
- Why: People type part of a name ("frieren"), in either language. Ordering by members puts
  the main series first: Sousou no Frieren (1,527,369 members), then the 2nd Season, then a
  short special. A scan of 27,054 titles took about 20 ms, so no search index is needed.
- Alternatives considered: Exact title match (too strict); fuzzy matching for typos (a new
  dependency, not needed yet); ordering by score (puts small, highly rated specials first).
- Trade-off: No typo tolerance: "freiren" finds nothing.
- Interview one-liner: "Search is a case-insensitive substring match on both titles, with the
  most-watched shows first, which is fast enough in memory at this size."

## D-054: The API's own requirements file includes python-dotenv
- Component: 5
- Decision: `api/requirements.txt` holds fastapi, uvicorn[standard], pandas, and pyarrow, plus
  python-dotenv, all at the same versions as the root `requirements.txt`.
- Why: The project reads settings from environment variables or a `.env` file, and the API
  reads `ANIPULSE_DATA_DIR` the same way. python-dotenv is tiny and already a project
  dependency, so the API keeps the same configuration rule as the rest of the code.
- Alternatives considered: Reading only real environment variables in the API (a second way
  to configure things, just for one package).
- Trade-off: One more package in the hosting install.
- Interview one-liner: "The API host installs only five packages, not the analysis stack."

## D-055: The dashboard reads the prebuilt files and reuses the API's lookup code
- Component: 6
- Decision: The Streamlit dashboard loads `data/processed/` directly with `st.cache_data`. It
  does not call the API or Postgres. It reuses `api/data.py` for loading, search, and
  recommendations, so both front ends give the same answer to the same question.
- Why: A free API host sleeps when idle, and a 30 to 60 second wake-up would stall a demo. The
  files are small and already built for the API (D-050). Sharing `search` and `recommend`
  means a fix to one is a fix to both.
- Alternatives considered: Calling the API over HTTP (cold starts, and two things to keep
  running); querying Postgres (needs a hosted database).
- Trade-off: The dashboard depends on `api/data.py`, so a change there affects both. It imports
  only that module (loaders, lookups, and the data notice), never the FastAPI app in
  `api/main.py`, so the dashboard runs without FastAPI. Data is only as fresh as the last
  rebuild.
- Interview one-liner: "The dashboard and the API read the same files through the same
  functions, so they can't disagree and neither waits on the other."

## D-056: Episodes and episode length are charted as buckets, saved by the analysis
- Component: 6
- Decision: The analysis now also writes `analysis/numeric_bins.parquet`: median score with a
  bootstrap 95% interval and n for episode buckets (1, 2-6, 7-13, 14-26, 27-52, 53+) and
  episode-length buckets in minutes (1-4, 5-14, 15-29, 30-59, 60+). The dashboard shows each
  chart with its Spearman rho from the existing tests.
- Why: A rho is one number. It says "more episodes, slightly higher score" (rho 0.19) but hides
  the shape. The buckets show it: 14-26 episodes has the highest median (7.03) and 2-6 the
  lowest (6.45), and for length, 60+ minutes is highest (7.11) while 30-59 minutes (6.37) is
  below 15-29 (6.92). The edges follow how anime is made: 12-13 episodes is one cour, 24-26 is
  two. The buckets are computed after every other result, so the earlier bootstrap intervals
  did not change: rerunning the analysis rewrote every other table byte for byte.
- Alternatives considered: Shipping every title's episodes and length to the dashboard (more
  data to ship for one chart); showing only the rho (no shape).
- Trade-off: Bucket edges are a choice, and different edges would give slightly different
  pictures.
- Interview one-liner: "Correlation gave me one number, so I added bucketed medians with
  intervals to show where the relationship actually bends."

## D-057: The headline sentence is saved by the analysis, not rebuilt by the dashboard
- Component: 6
- Decision: `python -m analysis.run` writes `analysis/summary.json` with the headline sentence
  from FINDINGS.md, the cross-validated R squared, the model's n, the population n, and the
  top-250 n. The Overview and "What predicts a high score?" pages show the sentence word for
  word.
- Why: The model fit lived only in memory, so the dashboard had no way to state it. Writing
  the sentence once means FINDINGS.md and the dashboard can never drift apart. The top-250
  count is saved too because ties at the cutoff make it 253, not 250 (D-040).
- Alternatives considered: Rebuilding the sentence in the dashboard (two copies of the same
  logic); adding the fit to `metadata.json` (that file describes the data, not the results).
- Trade-off: One more file in `data/processed/analysis/`.
- Interview one-liner: "The headline is written once by the analysis and displayed everywhere,
  so every page says exactly what the report says."

## D-058: One chart style: medians as dots, and the title's subject in the accent color
- Component: 6
- Decision: Every chart goes through `dashboard/style.py`. The mark the title talks about is
  accent blue (#2a78d6) and the rest are muted gray (#c3c2b7). A chart comparing two series
  uses gray for the context series and blue for the one the title is about; orange (#eb6834)
  is held for a second colored series. `.streamlit/config.toml` uses the same blue. Median
  scores are drawn as dots with 95% interval whiskers, not bars. Every chart title states the
  takeaway and n, and the caption names the data source.
- Why: Readers look where the color is, so the color should point at the claim. Blue and orange
  were run through a palette checker: they stay far apart for the common kinds of color
  blindness (a color difference of 24.7, where 8 is the target), and gray carries no hue.
  Dots, because medians sit between about 6 and 7.5: a bar starting at 0 makes 6.4 and 6.9
  look the same, and a bar that doesn't start at 0 exaggerates the gap.
- Alternatives considered: Plotly's default colors (a new color per bar, with nothing
  standing out); bar charts of medians (see above).
- Trade-off: Muted bars are harder to compare with each other than fully colored ones; hover
  tooltips give the exact numbers.
- Interview one-liner: "Each chart's title makes one claim, and the only colored mark is the
  one the claim is about."

## D-059: The recommender page labels match_score as a rank and explains empty lists
- Component: 6
- Decision: match_score is shown as "Match rank in this list (0-1)", with three decimals, a
  bar, a help tooltip, and a caption saying it is not a percentage match and should not be
  compared across titles (D-051). A title with no recommendations gets a friendly message
  that says why, instead of an empty table.
- Why: Across all lists the median match_score is 0.991, and 56% of picks score 0.99 or more,
  so a label like "99% match" would mislead. Three decimals keep picks apart that two
  decimals would round to the same value (Frieren's first pick is 0.995). All 27 titles with
  no picks have no usable synopsis, and 26 of them have no genres or tags, so there is
  nothing to compare them with (D-052).
- Alternatives considered: Showing only the rank (loses how close the picks are); hiding
  titles with no picks from search (a real show would look missing).
- Trade-off: The page needs a caption to explain one number.
- Interview one-liner: "The score is a rank inside one show's list, so the dashboard labels it
  that way and says why a few shows have no picks."

## D-060: Every page has an AppTest smoke test on tiny files
- Component: 6
- Decision: `tests/test_dashboard.py` runs the app with Streamlit's AppTest, switches to each
  page, and fails on any exception. The analysis tables in those tests are built by the real
  `analyze()` on the synthetic test data, and the catalog and recommendations are the API
  tests' 6-title files. The pure helpers in `dashboard/logic.py` have their own unit tests.
- Why: A page that crashes is the worst demo bug, and AppTest runs pages without a browser:
  the five page tests take about 4.5 seconds together. Building the tables with the real
  analysis code means a change to a table's columns breaks these tests, not the live
  dashboard.
- Alternatives considered: Browser tests with Playwright (slower, needs a running server);
  testing only the helpers (misses errors in page layout code).
- Trade-off: Smoke tests prove a page runs, not that a chart is right; the helpers' unit tests
  and a look at the real app cover that.
- Interview one-liner: "Every page is run in the test suite against small fixture files, so a
  broken page fails a test before anyone sees it."

## D-061: Explore filters treat "everything" as no filter
- Component: 6
- Decision: On the Explore page, an empty type list, no genre, no studio, and the full year
  range all mean "don't filter". Titles with no year are shown only while the year slider
  covers every year. Minimum members starts at 1,000, the same cutoff the analysis uses.
- Why: Leaving the slider alone should not quietly hide titles without a year, but narrowing
  it to 2020-2023 should not show undated ones either. Starting at 1,000 members hides
  thousands of near-unknown titles that would crowd the top of any sort by score.
- Alternatives considered: A separate "include unknown year" checkbox (one more control for a
  rare case).
- Trade-off: Someone looking for an obscure title must lower the members filter first.
- Interview one-liner: "Filters only filter when you touch them, and the default view matches
  the analysis population's member cutoff."

## D-062: The data refreshes weekly, not daily
- Component: 7
- Decision: The refresh workflow runs every Monday at 13:17 UTC, plus on demand from the
  Actions tab.
- Why: Each refresh adds a commit to `main`. Daily commits would bury the
  one-commit-per-component history under hundreds of "data: weekly refresh" commits. MyAnimeList
  scores move slowly, so a week of staleness changes almost nothing in the findings. The odd
  minute (13:17) avoids the top of the hour, when GitHub's scheduler is busiest and delays runs.
- Alternatives considered: Daily (noisy history, about 7 times the repo growth). Monthly (the
  dashboard's "last updated" date would look abandoned).
- Trade-off: Data can be up to a week old.
- Interview one-liner: "Weekly matches how fast scores actually change and keeps the git history
  readable."

## D-063: The refresh commits FINDINGS.md along with data/processed/
- Component: 7
- Decision: The refresh commit includes `analysis/FINDINGS.md` as well as `data/processed/`.
- Why: `python -m analysis.run` rewrites FINDINGS.md from the database. If only the data files
  were committed, the first refresh that moved a number would leave the written findings
  describing older data than the dashboard shows.
- Alternatives considered: Committing only `data/processed/` and regenerating FINDINGS.md by
  hand (it would drift without anyone noticing).
- Trade-off: FINDINGS.md changes every week, at least its "Data last updated" line.
- Interview one-liner: "The report and the data are written by the same run and committed
  together, so they can't disagree."

## D-064: CI runs the database tests against a real Postgres 16
- Component: 7
- Decision: The CI job starts a `postgres:16` service container and sets `DATABASE_URL`, so the
  tests marked `db` (loading, upserts, the analysis SQL) run on every push instead of being
  skipped.
- Why: Those tests check things only a real database can: `ON CONFLICT` upserts, foreign keys,
  and the exact SQL the analysis runs. Postgres 16 matches the version used locally and in
  `docker-compose.yml`. A health check makes the job wait until the database accepts
  connections.
- Alternatives considered: Skipping `db` tests in CI (the riskiest code would go untested).
  SQLite (a different SQL dialect: the analysis queries use Postgres features such as `::` casts and aggregate functions SQLite lacks, and the loader uses the Postgres insert dialect).
- Trade-off: Each CI run spends a few seconds starting the container.
- Interview one-liner: "CI tests the SQL against the same database engine production uses, not
  a stand-in."

## D-065: Every refresh rebuilds from an empty database and usually commits
- Component: 7
- Decision: The workflow starts from an empty Postgres each week, loads everything, and commits
  if `git diff --cached --quiet` finds any change. It pushes with the built-in `GITHUB_TOKEN`
  as `github-actions[bot]`, after `git pull --rebase` in case `main` moved during the run.
- Why: A runner keeps nothing between runs, so rebuilding is the only option without paying
  for a hosted database. Because every row gets a fresh `updated_at`, `metadata.json` and
  FINDINGS.md always change, so in practice there is a commit every week. That is honest: the
  data really was refreshed. A push made with `GITHUB_TOKEN` does not start other workflows,
  so the data commit cannot trigger CI or another refresh.
- Alternatives considered: Ignoring changes that only touch timestamps (more code to decide
  what "really" changed, for little gain). A hosted database (costs money, and needs a secret).
- Trade-off: Repo growth. Today the committed files total about 2.3 MB (catalog.parquet 1.3 MB,
  recommendations.parquet 0.9 MB, the rest under 0.1 MB). Parquet is already compressed, so a
  week where both big files change adds about 2.3 MB, at most about 120 MB a year. In a local
  rehearsal of one refresh, all 16 files changed.
- Interview one-liner: "Runners are stateless, so the refresh rebuilds from scratch and commits
  the result. The bot's token can't trigger workflows, so it can't loop."

## D-066: The pipeline's exit code decides whether the refresh fails
- Component: 7
- Decision: The workflow runs `python -m pipeline.run` as a normal step, with no
  `continue-on-error`.
- Why: The pipeline already returns 0 when the live API is down (it logs the failed pages and
  keeps the CSV data) and 1 when the CSV base load fails. So an API outage produces a normal
  refresh from the CSV, and a broken base load stops the job before anything is committed.
- Alternatives considered: `continue-on-error` on the load step (it would also hide a failed
  base load and commit empty or stale files).
- Trade-off: Someone has to read the run's log to notice that the API part failed, because the
  run still shows green.
- Interview one-liner: "The failure policy lives in the code's exit codes, so the workflow
  stays a plain list of commands."

## D-067: Use the newest major versions of the GitHub actions
- Component: 7
- Decision: Both workflows use `actions/checkout@v7` and `actions/setup-python@v7`.
- Why: GitHub removed Node 20 from its runners in September 2026, so older action versions
  built on it no longer run. v7's changes don't affect these workflows: checkout v7 only blocks
  fork code under `pull_request_target` and `workflow_run` (not used here), and setup-python
  v7 only removed the `pip-install` input (not used here). `python-version-file` reads
  `.python-version`, so CI and local development use the same Python.
- Alternatives considered: Pinning each action to a commit SHA (safer against a tampered tag,
  but harder for a reader to see which version runs).
- Trade-off: A major-version tag moves when the action publishes fixes, so a run can change
  without a commit here.
- Interview one-liner: "Current major versions, and Python comes from the same file the
  developers use."

## D-068: One Dockerfile with two targets, and the pipeline image runs the mounted repo
- Component: 8
- Decision: The Dockerfile has a shared `base` stage and two targets. `api` (the default)
  copies only `api/` and `data/processed/` and runs as a non-root user. `pipeline` installs
  the full `requirements.txt` but copies no code. `docker-compose.yml` mounts the repo into it
  and runs the same four commands as the weekly refresh, with `--api-pages 4`.
- Why: The API needs 5 packages and 2.3 MB of data. The pipeline needs scipy, statsmodels,
  scikit-learn, and the 9 MB dataset. One image for both would ship all of that to the host.
  Mounting the repo means a local pipeline run writes its outputs where the refresh writes
  them, so `git diff` shows exactly what changed, for example Frieren's (mal_id 52991) new
  member count in `catalog.parquet`.
- Alternatives considered: Two Dockerfiles (two files to keep in step on the Python version).
  Copying the code into the pipeline image (outputs would stay inside the container unless
  each output folder were mounted).
- Trade-off: The pipeline image is only useful next to a checkout of the repo. Its outputs
  overwrite committed files, so a local run must be undone with
  `git restore data/processed analysis/FINDINGS.md` before the next `git pull`.
- Interview one-liner: "Same base, two targets: a lean non-root API image, and a pipeline image
  that runs whatever code is in my working copy."

## D-069: `.dockerignore` lists what to send, not what to skip
- Component: 8
- Decision: `.dockerignore` starts with `*` (ignore everything), then allows `api/`,
  `data/processed/`, and `requirements.txt`.
- Why: Everything sent to Docker can end up in an image. With an allowlist, a new file such as
  `.env` (which holds `DATABASE_URL`) or a large dump in `data/raw/` is left out unless someone
  adds it on purpose. It also keeps the build context small: the 9 MB dataset and `.git` are
  never sent.
- Alternatives considered: A denylist of `.env`, `.venv`, `.git`, and so on (every new file is
  included until someone remembers to list it).
- Trade-off: A new folder the image needs must be added in two places, the Dockerfile and
  `.dockerignore`. A test checks that the file still starts with `*` and never allows `.env`.
- Interview one-liner: "Default-deny for the build context, so secrets can't leak into an
  image by accident."

## D-070: Render runs the API on its Python runtime, with the version from `.python-version`
- Component: 8
- Decision: `render.yaml` uses `runtime: python` with `pip install -r api/requirements.txt` and
  uvicorn on `$PORT`, not the Dockerfile. It sets no `PYTHON_VERSION`, so Render reads `3.13`
  from `.python-version` and uses the newest 3.13 release.
- Why: The native runtime skips building a 640 MB image (measured) on every deploy, and its
  two commands are the same ones a reader runs locally. Render ranks `PYTHON_VERSION` above
  `.python-version` and needs a full version like `3.13.5` there, so setting it would create a
  second place to update. One file now sets Python for local development, CI
  (`python-version-file`), Docker (a test checks the Dockerfile's `ARG`), and Render.
- Alternatives considered: `runtime: docker` (a full image build on every deploy). Pinning
  `PYTHON_VERSION: 3.13.5` (exact, but drifts from `.python-version`).
- Trade-off: Render may move to a newer 3.13 patch release without a commit here. The Docker
  image is tested in CI but not what production runs.
- Interview one-liner: "Production uses the platform's Python runtime, and one file decides the
  Python version everywhere."

## D-071: Render deploys on every commit
- Component: 8
- Decision: `autoDeployTrigger: commit`.
- Why: The weekly refresh pushes with the workflow's own token, and GitHub starts no workflows
  for that push, so the data commit never gets CI checks. With `checksPass`, Render waits for
  checks to pass, and it is not clear that a commit with no checks would ever deploy. Then the
  live API could keep serving last week's data. The data commit only changes files that the
  next CI run on `main` covers.
- Alternatives considered: `checksPass` (safer for code changes, but risks never deploying the
  data refresh). `off` (every deploy by hand).
- Trade-off: A commit that breaks the API is deployed before CI finishes. Render's health check
  limits the damage: a deploy whose `/health` does not answer never receives traffic, and the
  previous deploy keeps serving.
- Interview one-liner: "Deploy on every commit, and let the health check stop a broken deploy
  from taking traffic."

## D-072: CI starts the API image and calls `/health`
- Component: 8
- Decision: A `docker` job in `ci.yml` validates `docker-compose.yml`, builds both targets, runs
  the API image, and calls `/health` with `curl` (up to 10 retries, one second apart).
- Why: A successful build only proves the files were copied. Starting the container also
  proves the image can import the app, find the data files, and listen on `$PORT`. For example,
  a typo in the start command (`api.mian:app`) builds fine, but the container stops with
  "Could not import module", so `/health` fails.
- Alternatives considered: Build only (what the spec requires, but it misses startup errors).
  `docker/build-push-action` (adds caching, but adds another action to keep up to date).
- Trade-off: About a minute of extra CI time per push, with no layer cache between runs.
- Interview one-liner: "CI doesn't just build the image, it boots it and checks that it
  answers."
