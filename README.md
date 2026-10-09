# AniPulse

An anime analytics platform that asks which factors known before an anime airs are associated
with a higher MyAnimeList score, and serves "if you liked X, try these" recommendations.

**Work in progress.**

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

Code is under the MIT License (see `LICENSE`). Data files are under the ODbL v1.0 (see
`DATA_LICENSE.md`).
