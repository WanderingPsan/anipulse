# AniPulse

[![CI](https://github.com/WanderingPsan/anipulse/actions/workflows/ci.yml/badge.svg)](https://github.com/WanderingPsan/anipulse/actions/workflows/ci.yml)

An anime analytics platform that asks which factors known before an anime airs are associated
with a higher MyAnimeList score, and serves "if you liked X, try these" recommendations.

**Work in progress.**

## Automation

- **CI** (`.github/workflows/ci.yml`): every push and pull request to `main` runs `ruff check`,
  `ruff format --check`, and the full test suite against a PostgreSQL 16 service container.
- **Weekly refresh** (`.github/workflows/refresh.yml`): every Monday at 13:17 UTC, and on demand,
  it reloads the Kaggle snapshot, refreshes the top 4 pages of anime from the Tenrai API,
  reruns the analysis and the recommender, and commits `data/processed/` and
  `analysis/FINDINGS.md` if they changed. A live API outage does not fail the run. A failed
  CSV load does.

## Run the API

The API serves the catalog and recommendations from the files in `data/processed/`. From the
repo root:

```
python -m pip install -r requirements-dev.txt
uvicorn api.main:app --reload
```

Then open http://127.0.0.1:8000/docs. Endpoints: `GET /health`, `GET /anime/search?q=`,
`GET /anime/{mal_id}`, and `GET /recommend/{mal_id}?k=10`. Set `ANIPULSE_DATA_DIR` to read the
files from another folder.

## Run with Docker

With Docker Desktop running, from the repo root:

```
docker compose up --build api
```

This builds the API image from `Dockerfile` (Python slim, non-root user, the API code and
`data/processed/` only) and serves it on http://127.0.0.1:8000. Stop it with Ctrl+C.

To rebuild the data the same way the weekly refresh does (create the tables, load the CSV and
4 pages from the Tenrai API, run the analysis and the recommender) against a Postgres
container:

```
docker compose run --rm pipeline
```

The outputs land in your own `data/processed/` and `analysis/FINDINGS.md`. The weekly refresh
commits those same files, so undo a local run before your next `git pull`, or the pull fails
with "local changes would be overwritten":

```
git restore data/processed analysis/FINDINGS.md
```

`render.yaml` describes the hosted API: a free Render web service that installs
`api/requirements.txt`, starts uvicorn on Render's `$PORT`, checks `/health` before switching
traffic to a new deploy, and takes its Python version from `.python-version`.

Code is under the MIT License (see `LICENSE`). Data files are under the ODbL v1.0 (see
`DATA_LICENSE.md`).
