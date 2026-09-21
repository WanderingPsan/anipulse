import time
import requests

BASE_URL = "https://api.jikan.moe/v4"

# Jikan allows 3 requests/second and 60/minute.
# Sleeping 0.5s between calls keeps us safely under both limits.
THROTTLE_SECONDS = 0.5
MAX_RETRIES = 3


def get(endpoint, params=None):
    """Send one GET request to Jikan, retrying on failure with backoff."""
    url = f"{BASE_URL}/{endpoint}"
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.get(url, params=params, timeout=20)
            response.raise_for_status()
            time.sleep(THROTTLE_SECONDS)
            return response.json()
        except requests.exceptions.RequestException as err:
            if attempt == MAX_RETRIES:
                raise  # out of tries — fail loudly
            wait = 2 ** (attempt - 1)  # 1s, then 2s, then 4s
            print(f"Attempt {attempt} failed ({err}). Retrying in {wait}s...")
            time.sleep(wait)


def get_top_anime(pages=1):
    """Fetch the top-rated anime, 25 per page."""
    results = []
    for page in range(1, pages + 1):
        data = get("top/anime", params={"page": page})
        results.extend(data["data"])
    return results
