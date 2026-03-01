# Last.fm Event Scrapper

Scrape and visualize all events from a Last.fm user profile.

## Setup

```bash
uv sync
```

Create a `.env` file with your Last.fm credentials (needed to avoid rate limits):

```
LASTFM_USERNAME=your_username
LASTFM_PASSWORD=your_password
```

## Usage

### 1. Scrape events

```bash
uv run python scrape.py "https://www.last.fm/user/mazman159/events" -o mazman159_events.yaml
```

Options:
- `-o FILE` — Output file (.yaml/.yml or .json)
- `--no-posters` — Skip downloading poster images
- `--force-posters` — Re-download all poster images even if cached

### 2. Render HTML page

```bash
uv run python render.py mazman159_events.yaml -o index.html
```

Options:
- `-o FILE` — Output HTML file (default: `index.html`)
- `--title NAME` — Page title (default: inferred from filename)

Then open `index.html` in your browser. The `images/` folder must be alongside it for posters to display.

## Resume Copilot session

To continue working on this project with the same context, run:

```bash
copilot
```

Then type `/resume` to pick the previous session.

Session ID: ce67cdb4-02df-460e-8beb-ea76be99174d