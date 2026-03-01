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

### All-in-one (scrape + render)

```bash
uv run python cli.py run "https://www.last.fm/user/mazman159/events"
```

This scrapes events to `mazman159_events.yaml` and generates `index.html` in one step.

Options:
- `-o FILE` — Events output file (default: `<username>_events.yaml`)
- `--html FILE` — HTML output file (default: `index.html`)
- `--title NAME` — Page title (default: inferred from filename)
- `--no-posters` — Skip downloading poster images
- `--force-posters` — Re-download all poster images even if cached

### Scrape only

```bash
uv run python cli.py scrape "https://www.last.fm/user/mazman159/events" -o mazman159_events.yaml
```

Options:
- `-o FILE` — Output file (.yaml/.yml or .json)
- `--no-posters` — Skip downloading poster images
- `--force-posters` — Re-download all poster images even if cached

### Render only

```bash
uv run python cli.py render mazman159_events.yaml -o index.html
```

Options:
- `-o FILE` — Output HTML file (default: `index.html`)
- `--title NAME` — Page title (default: inferred from filename)

Then open `index.html` in your browser. The `images/` folder must be alongside it for posters to display.

The standalone scripts `scrape.py` and `render.py` can still be used directly.

## Resume Copilot session

To continue working on this project with the same context, run:

```bash
copilot
```

Then type `/resume` to pick the previous session.

Session ID: ce67cdb4-02df-460e-8beb-ea76be99174d