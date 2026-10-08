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
