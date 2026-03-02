"""Scrape all events from a Last.fm user profile."""

import argparse
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import quote_plus

import requests
import yaml
from bs4 import BeautifulSoup
from dotenv import load_dotenv
import os

load_dotenv()

BASE_URL = "https://www.last.fm"

US_STATES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
    "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
    "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
    "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
    "DC",
}


def normalize_city(city: str) -> str:
    """Clean city names by removing region/state suffixes and zip codes.

    Examples: 'Seattle, WA' -> 'Seattle', 'Las Vegas, NV 89101' -> 'Las Vegas',
              'Seattle, Washington' -> 'Seattle'
    """
    # Take only the part before the first comma
    cleaned = city.split(",")[0].strip()
    # Also strip trailing US state abbreviation (without comma, e.g. 'Kent WA')
    match = re.match(r"^(.+?)\s+([A-Z]{2})(?:\s+\d{5}(?:-\d{4})?)?\s*$", cleaned)
    if match and match.group(2) in US_STATES:
        cleaned = match.group(1).strip()
    return cleaned

session = requests.Session()
session.headers.update({
    "Accept-Language": "en-US,en;q=0.5",
})


def parse_profile_url(url: str) -> str:
    """Extract username from a Last.fm profile/events URL."""
    match = re.match(r"https?://(?:www\.)?last\.fm/user/([^/]+)", url)
    if not match:
        raise ValueError(f"Invalid Last.fm profile URL: {url}")
    return match.group(1)


def login() -> bool:
    """Log in to Last.fm using credentials from .env file."""
    username = os.getenv("LASTFM_USERNAME")
    password = os.getenv("LASTFM_PASSWORD")
    if not username or not password:
        print("No LASTFM_USERNAME/LASTFM_PASSWORD set. Continuing without login.", file=sys.stderr)
        print("Warning: unauthenticated requests may get 406 errors on event detail pages.", file=sys.stderr)
        return False

    print(f"Logging in as {username} ...", file=sys.stderr)
    try:
        resp = session.get(f"{BASE_URL}/login", timeout=30)
        resp.raise_for_status()
    except requests.exceptions.RequestException as e:
        raise SystemExit(f"Error: could not reach login page: {e}")

    soup = BeautifulSoup(resp.text, "html.parser")
    csrf_input = soup.select_one("input[name='csrfmiddlewaretoken']")
    if not csrf_input:
        print("Warning: could not find CSRF token on login page.", file=sys.stderr)
        return False

    csrf_token = csrf_input["value"]
    try:
        login_resp = session.post(
            f"{BASE_URL}/login",
            data={
                "csrfmiddlewaretoken": csrf_token,
                "username_or_email": username,
                "password": password,
                "next": "/user/_",
            },
            headers={"Referer": f"{BASE_URL}/login"},
            timeout=30,
        )
        login_resp.raise_for_status()
    except requests.exceptions.RequestException as e:
        raise SystemExit(f"Error: login request failed: {e}")

    if login_resp.url != f"{BASE_URL}/login":
        print("Logged in successfully.", file=sys.stderr)
        return True
    else:
        print("Warning: login failed (redirected back to login page).", file=sys.stderr)
        return False


def fetch_page(url: str, retries: int = 3) -> BeautifulSoup:
    for attempt in range(retries):
        if attempt > 0:
            wait = 30 * (attempt + 1)
            print(f"  Rate limited, waiting {wait}s before retry...", file=sys.stderr)
            time.sleep(wait)
        time.sleep(5)
        try:
            resp = session.get(url, timeout=30)
        except requests.exceptions.ReadTimeout:
            print(f"  Timeout fetching {url}" + (", retrying..." if attempt < retries - 1 else ""), file=sys.stderr)
            if attempt < retries - 1:
                continue
            raise SystemExit(f"Error: timed out fetching {url} after {retries} attempts")
        except requests.exceptions.ConnectionError:
            print(f"  Connection error for {url}" + (", retrying..." if attempt < retries - 1 else ""), file=sys.stderr)
            if attempt < retries - 1:
                continue
            raise SystemExit(f"Error: could not connect to {url} after {retries} attempts")
        if resp.status_code == 406 and attempt < retries - 1:
            continue
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "html.parser")


def artist_name_to_url(name: str) -> str:
    """Convert an artist name to a Last.fm music URL."""
    slug = name.strip().replace(" ", "+")
    return f"{BASE_URL}/music/{quote_plus(name.strip(), safe='+')}"


def extract_year_links(soup: BeautifulSoup, username: str) -> list[str]:
    """Extract year page URLs from the event year navigation."""
    years = []
    for link in soup.select('nav[aria-label="Event Year Navigation"] a'):
        href = link.get("href", "")
        if re.search(r"/events/\d{4}$", href):
            years.append(BASE_URL + href)
    return years


def extract_events(soup: BeautifulSoup) -> list[dict]:
    """Extract events from a single page (list view)."""
    events = []
    for row in soup.select("tr.events-list-item"):
        event = {}

        # Date as YYYY-MM-DD
        time_el = row.select_one("time.calendar-icon")
        if time_el:
            dt = time_el.get("datetime", "")
            event["date"] = dt[:10] if len(dt) >= 10 else dt

        # Title and URL
        title_link = row.select_one(".events-list-item-event--title a")
        if title_link:
            event["title"] = title_link.get_text(strip=True)
            event["url"] = BASE_URL + title_link.get("href", "")

        # Lineup with constructed Last.fm URLs
        lineup_el = row.select_one(".events-list-item-event--lineup")
        if lineup_el:
            artists = [a.strip() for a in lineup_el.get_text().split(",") if a.strip()]
            event["lineup"] = [
                {"name": name, "url": artist_name_to_url(name)} for name in artists
            ]

        # Venue
        venue_title = row.select_one(".events-list-item-venue--title")
        if venue_title:
            event["venue"] = venue_title.get_text(strip=True)

        venue_city = row.select_one(".events-list-item-venue--city")
        if venue_city:
            event["city"] = venue_city.get_text(strip=True)
            event["city_clean"] = normalize_city(event["city"])

        venue_country = row.select_one(".events-list-item-venue--country")
        if venue_country:
            event["country"] = venue_country.get_text(strip=True)

        if event:
            events.append(event)

    return events


def extract_event_details(event_url: str) -> dict:
    """Fetch an event detail page and extract lineup with links + poster URL."""
    soup = fetch_page(event_url)
    details = {}

    # Lineup with Last.fm links from header-title-secondary
    header_secondary = soup.select_one(".header-title-secondary")
    if header_secondary:
        lineup = []
        for a_tag in header_secondary.select("a[href^='/music/']"):
            lineup.append({
                "name": a_tag.get_text(strip=True),
                "url": BASE_URL + a_tag.get("href", ""),
            })
        if lineup:
            details["lineup"] = lineup

    # Poster image (full resolution from the expand view)
    poster_img = soup.select_one("img.event-expanded-image") or soup.select_one("img.event-poster-preview")
    if poster_img:
        src = poster_img.get("src", "")
        if src:
            details["poster_url"] = src

    return details


def find_existing_image(images_dir: Path, event_id: str) -> str | None:
    """Check if an image already exists for this event_id (any extension)."""
    for ext in (".jpg", ".png", ".webp", ".gif"):
        filepath = images_dir / f"{event_id}{ext}"
        if filepath.exists():
            return f"images/{event_id}{ext}"
    return None


def download_image(url: str, images_dir: Path, event_id: str, force: bool = False) -> str | None:
    """Download an image and return the relative path. Falls back to thumbnail if full-res 404s."""
    if not force:
        existing = find_existing_image(images_dir, event_id)
        if existing:
            return existing

    for attempt_url in [url, url.replace("/ar0/", "/arXL/")]:
        try:
            resp = session.get(attempt_url, timeout=30)
            resp.raise_for_status()
        except requests.RequestException:
            continue

        # Determine extension from content-type
        content_type = resp.headers.get("content-type", "")
        ext = ".jpg"
        if "png" in content_type:
            ext = ".png"
        elif "webp" in content_type:
            ext = ".webp"
        elif "gif" in content_type:
            ext = ".gif"

        filename = f"{event_id}{ext}"
        filepath = images_dir / filename
        filepath.write_bytes(resp.content)
        return f"images/{filename}"

    print(f"  Warning: failed to download poster: {url}", file=sys.stderr)
    return None


def scrape_user_events(username: str, images_dir: Path | None = None, force_posters: bool = False) -> list[dict]:
    """Scrape all events (upcoming + all past years) for a user."""
    events_url = f"{BASE_URL}/user/{username}/events"
    print(f"Fetching {events_url} ...", file=sys.stderr)
    soup = fetch_page(events_url)

    all_events = extract_events(soup)

    # Discover and scrape each year page
    year_urls = extract_year_links(soup, username)
    for year_url in year_urls:
        print(f"Fetching {year_url} ...", file=sys.stderr)
        year_soup = fetch_page(year_url)
        all_events.extend(extract_events(year_soup))

    # Fetch event detail pages for posters (if images_dir is set)
    if images_dir is not None:
        for i, event in enumerate(all_events):
            url = event.get("url")
            if not url:
                continue
            event_id = url.rstrip("/").split("/")[-1].split("+")[0]

            # Skip network request if image already cached
            if not force_posters:
                existing = find_existing_image(images_dir, event_id)
                if existing:
                    print(f"  [{i+1}/{len(all_events)}] Cached: {event.get('title', '?')}", file=sys.stderr)
                    event["poster"] = existing
                    continue

            print(f"  [{i+1}/{len(all_events)}] Poster for {event.get('title', '?')} ...", file=sys.stderr)
            try:
                details = extract_event_details(url)
            except requests.RequestException as e:
                print(f"    Skipped: {e}", file=sys.stderr)
                continue

            if "poster_url" in details:
                rel_path = download_image(details["poster_url"], images_dir, event_id, force=force_posters)
                if rel_path:
                    event["poster"] = rel_path

    return all_events


def run_scrape(profile_url: str, output: str | None = None, no_posters: bool = False, force_posters: bool = False):
    """Run the scraper with the given options. Returns the list of events."""
    username = parse_profile_url(profile_url)
    login()

    images_dir = None
    if output and not no_posters:
        output_dir = Path(output).parent
        images_dir = output_dir / "images"
        images_dir.mkdir(parents=True, exist_ok=True)

    events = scrape_user_events(username, images_dir, force_posters=force_posters)

    if output:
        with open(output, "w") as f:
            if output.endswith((".yaml", ".yml")):
                yaml.dump(events, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
            else:
                json.dump(events, f, indent=2)
        print(f"Wrote {len(events)} events to {output}", file=sys.stderr)
    else:
        print(json.dumps(events, indent=2))

    return events


def main():
    parser = argparse.ArgumentParser(description="Scrape Last.fm user events and download poster images")
    parser.add_argument(
        "profile_url",
        help="Last.fm profile or events URL, e.g. https://www.last.fm/user/mazman159/events",
    )
    parser.add_argument(
        "-o", "--output",
        help="Output file path. Format is inferred from extension (.yaml/.yml or .json). Poster images are saved to an images/ folder next to this file. Defaults to JSON on stdout (no images).",
    )
    parser.add_argument(
        "--no-posters", action="store_true",
        help="Skip downloading event poster images.",
    )
    parser.add_argument(
        "--force-posters", action="store_true",
        help="Re-download all poster images even if they already exist.",
    )
    args = parser.parse_args()
    run_scrape(args.profile_url, args.output, args.no_posters, args.force_posters)


if __name__ == "__main__":
    main()
