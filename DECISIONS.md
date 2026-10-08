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
