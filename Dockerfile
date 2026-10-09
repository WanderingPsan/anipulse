# Two images from one file. Pick one with --target:
#   api       (the default) serves the prebuilt files in data/processed/
#   pipeline  rebuilds those files from the dataset and the live anime API
#
# Keep this Python version in step with .python-version (a test checks it).
ARG PYTHON_VERSION=3.13

FROM python:${PYTHON_VERSION}-slim AS base
# No .pyc files (they would land in the mounted repo), log lines appear at once, and pip
# keeps no download cache, which only makes the image bigger.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1
WORKDIR /app


FROM base AS pipeline
# Only the dependencies live in this image. docker-compose.yml mounts the repo at /app, so the
# pipeline runs the current code and writes its outputs straight into the repo folder.
COPY requirements.txt .
RUN pip install -r requirements.txt


FROM base AS api
# Requirements before code: Docker reuses this slow layer until the requirements change.
COPY api/requirements.txt api/requirements.txt
RUN pip install -r api/requirements.txt
# Run as a normal user, so a bug in the app can't change anything owned by root.
RUN useradd --create-home app
COPY api/ api/
COPY data/processed/ data/processed/
USER app
# Hosts like Render choose the port through $PORT. 8000 is the local default.
ENV PORT=8000
EXPOSE 8000
# sh -c fills in $PORT. exec makes uvicorn the main process, so docker stop reaches it.
CMD ["sh", "-c", "exec uvicorn api.main:app --host 0.0.0.0 --port ${PORT}"]
