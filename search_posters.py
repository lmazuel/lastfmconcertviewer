"""Search for missing event posters using Bing Image Search."""

import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import quote_plus

import requests
import yaml
from bs4 import BeautifulSoup

_SESSION = requests.Session()
_SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
})


def _slugify(text: str) -> str:
    """Convert text to a filesystem-safe slug."""
    text = text.lower().strip()
    text = re.sub(r"[''`]", "", text)
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_")


def _extract_headliner(event: dict) -> str:
    """Extract the headliner/main artist name from an event.

    With correct lineup data (headliner first from the detail page),
    the first lineup entry is the headliner.  Falls back to the event
    title when no lineup is available.
    """
    lineup = event.get("lineup", [])
    if lineup:
        return lineup[0]["name"] if isinstance(lineup[0], dict) else lineup[0]
    return event.get("title", "")


def _build_query(event: dict) -> str:
    """Build a search query from event data."""
    headliner = _extract_headliner(event)
    year = event.get("date", "")[:4]
    query = headliner
    # Only append year if not already in the name
    if year and year not in headliner:
        query += f" {year}"
    query += " tour poster"
    return query


def _build_filename(event: dict) -> str:
    """Build a descriptive filename from event data."""
    headliner = _extract_headliner(event)
    year = event.get("date", "")[:4]
    slug = _slugify(headliner)
    # Only append year if not already in the slug
    if year and year not in slug:
        slug += f"_{year}"
    return slug


def search_images(query: str, max_results: int = 5) -> list[dict]:
    """Search Bing for large images matching the query."""
    url = f"https://www.bing.com/images/search?q={quote_plus(query)}&qft=+filterui:imagesize-large"
    try:
        resp = _SESSION.get(url, timeout=15)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"    Search failed: {e}", file=sys.stderr)
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    results = []
    for tag in soup.select("a.iusc"):
        m = tag.get("m")
        if not m:
            continue
        try:
            data = json.loads(m)
        except json.JSONDecodeError:
            continue
        image_url = data.get("murl", "")
        if image_url:
            results.append({"url": image_url})
        if len(results) >= max_results:
            break
    return results


def download_first_valid(results: list[dict], filepath_base: str) -> str | None:
    """Try downloading images until one succeeds. Returns saved path."""
    for result in results:
        url = result["url"]
        try:
            resp = _SESSION.get(url, timeout=20)
            resp.raise_for_status()
        except requests.RequestException:
            continue

        content_type = resp.headers.get("content-type", "")
        if "png" in content_type:
            ext = ".png"
        elif "webp" in content_type:
            ext = ".webp"
        elif "gif" in content_type:
            ext = ".gif"
        else:
            ext = ".jpg"

        # Skip tiny files (likely broken/placeholder)
        if len(resp.content) < 5000:
            continue

        filepath = Path(f"{filepath_base}{ext}")
        filepath.write_bytes(resp.content)
        return str(filepath)
    return None


def run_search_posters(input_path: str, output_dir: str = "posters_review"):
    """Search for missing posters and save them to a review folder."""
    with open(input_path) as f:
        if input_path.endswith((".yaml", ".yml")):
            events = yaml.safe_load(f) or []
        else:
            events = json.load(f)

    missing = [e for e in events if "poster" not in e]
    print(f"Found {len(missing)} events without posters out of {len(events)} total.", file=sys.stderr)

    if not missing:
        print("Nothing to search for.", file=sys.stderr)
        return

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    found = 0
    for i, event in enumerate(missing):
        title = event.get("title", "?")
        query = _build_query(event)
        base_name = _build_filename(event)
        filepath_base = str(out / base_name)

        # Skip if already downloaded in review folder
        existing = list(out.glob(f"{base_name}.*"))
        if existing:
            print(f"  [{i+1}/{len(missing)}] Already found: {title}", file=sys.stderr)
            found += 1
            continue

        print(f"  [{i+1}/{len(missing)}] Searching: {title} ...", file=sys.stderr)
        print(f"    Query: {query}", file=sys.stderr)

        results = search_images(query)
        if not results:
            print(f"    No results found", file=sys.stderr)
            time.sleep(2)
            continue

        path = download_first_valid(results, filepath_base)
        if path:
            print(f"    Saved: {path}", file=sys.stderr)
            found += 1
        else:
            print(f"    Could not download any result", file=sys.stderr)

        time.sleep(2)  # Be polite to Bing

    print(f"\nDone: {found}/{len(missing)} posters found, saved to {output_dir}/", file=sys.stderr)
