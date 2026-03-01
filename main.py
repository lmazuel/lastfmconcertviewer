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
        print("No LASTFM_USERNAME/LASTFM_PASSWORD in .env, continuing without login.", file=sys.stderr)
        return False

    print(f"Logging in as {username} ...", file=sys.stderr)
    # Get CSRF token from login page
    resp = session.get(f"{BASE_URL}/login", timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    csrf_input = soup.select_one("input[name='csrfmiddlewaretoken']")
    if not csrf_input:
        print("Warning: could not find CSRF token on login page.", file=sys.stderr)
        return False

    csrf_token = csrf_input["value"]
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
        resp = session.get(url, timeout=30)
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

    # Poster image
    poster_img = soup.select_one("img.event-poster-preview")
    if poster_img:
        src = poster_img.get("src", "")
        if src:
            details["poster_url"] = src

    return details


def download_image(url: str, images_dir: Path, event_id: str) -> str | None:
    """Download an image and return the relative path."""
    try:
        resp = session.get(url, timeout=30)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"  Warning: failed to download poster: {e}", file=sys.stderr)
        return None

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


def scrape_user_events(username: str, images_dir: Path | None = None) -> list[dict]:
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
            print(f"  [{i+1}/{len(all_events)}] Poster for {event.get('title', '?')} ...", file=sys.stderr)
            try:
                details = extract_event_details(url)
            except requests.RequestException as e:
                print(f"    Skipped: {e}", file=sys.stderr)
                continue

            if "poster_url" in details:
                event_id = url.rstrip("/").split("/")[-1].split("+")[0]
                rel_path = download_image(details["poster_url"], images_dir, event_id)
                if rel_path:
                    event["poster"] = rel_path

    return all_events


def main():
    parser = argparse.ArgumentParser(description="Scrape Last.fm user events")
    parser.add_argument(
        "profile_url",
        help="Last.fm profile or events URL, e.g. https://www.last.fm/user/mazman159/events",
    )
    parser.add_argument(
        "-o", "--output",
        help="Output file path. Format is inferred from extension (.yaml/.yml or .json). Defaults to JSON on stdout.",
    )
    parser.add_argument(
        "--no-posters", action="store_true",
        help="Skip downloading event poster images.",
    )
    args = parser.parse_args()

    username = parse_profile_url(args.profile_url)
    login()

    # Create images dir relative to output file if specified
    images_dir = None
    if args.output and not args.no_posters:
        output_dir = Path(args.output).parent
        images_dir = output_dir / "images"
        images_dir.mkdir(parents=True, exist_ok=True)

    events = scrape_user_events(username, images_dir)

    if args.output:
        with open(args.output, "w") as f:
            if args.output.endswith((".yaml", ".yml")):
                yaml.dump(events, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
            else:
                json.dump(events, f, indent=2)
        print(f"Wrote {len(events)} events to {args.output}", file=sys.stderr)
    else:
        print(json.dumps(events, indent=2))


if __name__ == "__main__":
    main()
