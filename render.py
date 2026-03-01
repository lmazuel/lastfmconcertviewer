"""Render scraped Last.fm events as a static HTML page."""

import argparse
import base64
import json
import mimetypes
import sys
from pathlib import Path

import yaml
from jinja2 import Template

HTML_TEMPLATE = Template("""\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{ title }}</title>
<style>
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

:root {
  --bg: #0d0d0d;
  --bg-card: #1a1a2e;
  --bg-card-hover: #22223a;
  --bg-filter: #16213e;
  --accent: #e94560;
  --accent2: #0f3460;
  --text: #eee;
  --text-muted: #999;
  --text-dim: #666;
  --radius: 12px;
  --shadow: 0 4px 24px rgba(0,0,0,.5);
}

body {
  font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
  background: var(--bg);
  color: var(--text);
  line-height: 1.5;
  min-height: 100vh;
}

/* ── Header ── */
.hero {
  background: linear-gradient(135deg, #0f3460 0%, #1a1a2e 50%, #e94560 150%);
  padding: 3rem 1.5rem 2rem;
  text-align: center;
}
.hero h1 {
  font-size: 2.5rem;
  font-weight: 800;
  letter-spacing: -1px;
  margin-bottom: .3rem;
}
.hero h1 span { color: var(--accent); }
.hero .subtitle {
  color: var(--text-muted);
  font-size: 1.1rem;
}

/* ── Filters ── */
.filters {
  position: sticky;
  top: 0;
  z-index: 100;
  background: rgba(13,13,13,.92);
  backdrop-filter: blur(12px);
  border-bottom: 1px solid #222;
  padding: 1rem 1.5rem;
}
.filters-inner {
  max-width: 1400px;
  margin: 0 auto;
  display: flex;
  flex-wrap: wrap;
  gap: .75rem;
  align-items: center;
}
.search-box {
  flex: 1 1 280px;
  position: relative;
}
.search-box input {
  width: 100%;
  padding: .65rem 1rem .65rem 2.5rem;
  border: 1px solid #333;
  border-radius: 8px;
  background: #111;
  color: var(--text);
  font-size: .95rem;
  outline: none;
  transition: border-color .2s;
}
.search-box input:focus { border-color: var(--accent); }
.search-box::before {
  content: '🔍';
  position: absolute;
  left: .75rem;
  top: 50%;
  transform: translateY(-50%);
  font-size: .9rem;
  pointer-events: none;
}
.filter-group {
  display: flex;
  gap: .5rem;
  align-items: center;
}
.filter-group label {
  font-size: .8rem;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: .5px;
  white-space: nowrap;
}
.filter-group select {
  padding: .5rem .75rem;
  border: 1px solid #333;
  border-radius: 8px;
  background: #111;
  color: var(--text);
  font-size: .9rem;
  outline: none;
  cursor: pointer;
  max-width: 200px;
}
.filter-group select:focus { border-color: var(--accent); }
.stats {
  font-size: .85rem;
  color: var(--text-muted);
  margin-left: auto;
  white-space: nowrap;
}
.stats strong { color: var(--accent); }

/* ── Year nav ── */
.year-nav {
  max-width: 1400px;
  margin: 1.5rem auto .5rem;
  padding: 0 1.5rem;
  display: flex;
  flex-wrap: wrap;
  gap: .4rem;
}
.year-pill {
  padding: .3rem .8rem;
  border-radius: 20px;
  font-size: .8rem;
  font-weight: 600;
  background: var(--bg-filter);
  color: var(--text-muted);
  cursor: pointer;
  border: 1px solid transparent;
  transition: all .2s;
  text-decoration: none;
}
.year-pill:hover, .year-pill.active {
  background: var(--accent);
  color: #fff;
  border-color: var(--accent);
}

/* ── Grid ── */
.container {
  max-width: 1400px;
  margin: 0 auto;
  padding: 1rem 1.5rem 3rem;
}
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 1.25rem;
}

/* ── Cards ── */
.card {
  background: var(--bg-card);
  border-radius: var(--radius);
  overflow: hidden;
  box-shadow: var(--shadow);
  transition: transform .2s, box-shadow .2s;
  display: flex;
  flex-direction: column;
}
.card:hover {
  transform: translateY(-4px);
  box-shadow: 0 8px 32px rgba(233,69,96,.15);
}
.card-poster {
  width: 100%;
  aspect-ratio: 16/9;
  object-fit: cover;
  background: #111;
  display: block;
}
.card-poster-placeholder {
  width: 100%;
  aspect-ratio: 16/9;
  background: linear-gradient(135deg, #1a1a2e, #0f3460);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 3rem;
  opacity: .4;
}
.card-body { padding: 1rem 1.25rem 1.25rem; flex: 1; display: flex; flex-direction: column; }
.card-date {
  font-size: .75rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 1px;
  color: var(--accent);
  margin-bottom: .4rem;
}
.card-title {
  font-size: 1.1rem;
  font-weight: 700;
  margin-bottom: .5rem;
  line-height: 1.3;
}
.card-title a {
  color: var(--text);
  text-decoration: none;
}
.card-title a:hover { color: var(--accent); }
.card-lineup {
  display: flex;
  flex-wrap: wrap;
  gap: .35rem;
  margin-bottom: .75rem;
}
.artist-tag {
  display: inline-block;
  padding: .15rem .55rem;
  border-radius: 4px;
  font-size: .75rem;
  background: rgba(233,69,96,.12);
  color: #f0a0b0;
  text-decoration: none;
  transition: background .2s, color .2s;
  border: 1px solid rgba(233,69,96,.2);
}
.artist-tag:hover {
  background: var(--accent);
  color: #fff;
}
.card-venue {
  margin-top: auto;
  font-size: .82rem;
  color: var(--text-muted);
  display: flex;
  align-items: flex-start;
  gap: .4rem;
}
.card-venue::before {
  content: '📍';
  font-size: .75rem;
  flex-shrink: 0;
  margin-top: 1px;
}

/* ── Empty state ── */
.empty-state {
  grid-column: 1 / -1;
  text-align: center;
  padding: 4rem 1rem;
  color: var(--text-muted);
}
.empty-state .icon { font-size: 3rem; margin-bottom: 1rem; }
.empty-state p { font-size: 1.1rem; }

/* ── Year divider ── */
.year-divider {
  grid-column: 1 / -1;
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 1rem 0 .25rem;
}
.year-divider h2 {
  font-size: 1.6rem;
  font-weight: 800;
  color: var(--accent);
  white-space: nowrap;
}
.year-divider::after {
  content: '';
  flex: 1;
  height: 1px;
  background: linear-gradient(90deg, #333, transparent);
}

/* ── Responsive ── */
@media (max-width: 640px) {
  .hero h1 { font-size: 1.8rem; }
  .grid { grid-template-columns: 1fr; }
  .filters-inner { flex-direction: column; align-items: stretch; }
  .stats { margin-left: 0; text-align: center; }
}
</style>
</head>
<body>

<div class="hero">
  <h1>🎸 <span>{{ username }}</span>'s Shows</h1>
  <p class="subtitle">{{ total_events }} events from {{ min_year }} to {{ max_year }}</p>
</div>

<div class="filters">
  <div class="filters-inner">
    <div class="search-box">
      <input type="text" id="search" placeholder="Search bands, events, venues…" autocomplete="off">
    </div>
    <div class="filter-group">
      <label for="city-filter">City</label>
      <select id="city-filter"><option value="">All Cities</option></select>
    </div>
    <div class="filter-group">
      <label for="country-filter">Country</label>
      <select id="country-filter"><option value="">All Countries</option></select>
    </div>
    <div class="filter-group">
      <label for="time-filter">When</label>
      <select id="time-filter">
        <option value="">All Time</option>
        <option value="upcoming">Upcoming</option>
        <option value="past">Past</option>
      </select>
    </div>
    <div class="stats">
      <strong id="visible-count">{{ total_events }}</strong> / {{ total_events }} shows
    </div>
  </div>
</div>

<nav class="year-nav" id="year-nav"></nav>

<div class="container">
  <div class="grid" id="grid"></div>
</div>

<script>
const EVENTS = {{ events_json }};
const TODAY = new Date().toISOString().slice(0, 10);

const searchEl = document.getElementById('search');
const cityEl = document.getElementById('city-filter');
const countryEl = document.getElementById('country-filter');
const timeEl = document.getElementById('time-filter');
const gridEl = document.getElementById('grid');
const yearNavEl = document.getElementById('year-nav');
const countEl = document.getElementById('visible-count');

// Populate filters
const cities = [...new Set(EVENTS.map(e => e.city).filter(Boolean))].sort();
const countries = [...new Set(EVENTS.map(e => e.country).filter(Boolean))].sort();
const years = [...new Set(EVENTS.map(e => e.date?.slice(0,4)).filter(Boolean))].sort((a,b) => b-a);

cities.forEach(c => { const o = document.createElement('option'); o.value = c; o.textContent = c; cityEl.appendChild(o); });
countries.forEach(c => { const o = document.createElement('option'); o.value = c; o.textContent = c; countryEl.appendChild(o); });

// Year pills
years.forEach(y => {
  const pill = document.createElement('a');
  pill.className = 'year-pill';
  pill.textContent = y;
  pill.href = '#';
  pill.dataset.year = y;
  pill.addEventListener('click', e => {
    e.preventDefault();
    document.querySelectorAll('.year-pill').forEach(p => p.classList.remove('active'));
    if (pill.dataset.active === '1') { pill.dataset.active = ''; render(); return; }
    pill.classList.add('active');
    pill.dataset.active = '1';
    document.querySelectorAll('.year-pill').forEach(p => { if (p !== pill) p.dataset.active = ''; });
    render();
  });
  yearNavEl.appendChild(pill);
});

function formatDate(d) {
  if (!d) return '';
  const dt = new Date(d + 'T00:00:00');
  return dt.toLocaleDateString('en-US', { weekday: 'short', year: 'numeric', month: 'long', day: 'numeric' });
}

function escapeHtml(s) {
  const div = document.createElement('div');
  div.textContent = s;
  return div.innerHTML;
}

function matchSearch(event, query) {
  const q = query.toLowerCase();
  if (event.title?.toLowerCase().includes(q)) return true;
  if (event.venue?.toLowerCase().includes(q)) return true;
  if (event.city?.toLowerCase().includes(q)) return true;
  if (event.lineup?.some(a => a.name.toLowerCase().includes(q))) return true;
  return false;
}

function render() {
  const query = searchEl.value.trim();
  const cityFilter = cityEl.value;
  const countryFilter = countryEl.value;
  const timeFilter = timeEl.value;
  const yearPill = document.querySelector('.year-pill.active');
  const yearFilter = yearPill?.dataset.year || '';

  const filtered = EVENTS.filter(e => {
    if (query && !matchSearch(e, query)) return false;
    if (cityFilter && e.city !== cityFilter) return false;
    if (countryFilter && e.country !== countryFilter) return false;
    if (yearFilter && e.date?.slice(0,4) !== yearFilter) return false;
    if (timeFilter === 'upcoming' && e.date < TODAY) return false;
    if (timeFilter === 'past' && e.date >= TODAY) return false;
    return true;
  });

  countEl.textContent = filtered.length;
  gridEl.innerHTML = '';

  if (filtered.length === 0) {
    gridEl.innerHTML = '<div class="empty-state"><div class="icon">🎵</div><p>No shows match your filters</p></div>';
    return;
  }

  let lastYear = null;
  filtered.forEach(ev => {
    const year = ev.date?.slice(0,4) || '?';
    if (year !== lastYear) {
      lastYear = year;
      const divider = document.createElement('div');
      divider.className = 'year-divider';
      divider.innerHTML = '<h2>' + escapeHtml(year) + '</h2>';
      gridEl.appendChild(divider);
    }

    const card = document.createElement('div');
    card.className = 'card';

    let posterHtml;
    if (ev.poster) {
      posterHtml = '<img class="card-poster" src="' + escapeHtml(ev.poster) + '" alt="" loading="lazy">';
    } else {
      posterHtml = '<div class="card-poster-placeholder">🎶</div>';
    }

    const lineupHtml = (ev.lineup || []).map(a =>
      '<a class="artist-tag" href="' + escapeHtml(a.url) + '" target="_blank" rel="noopener">' + escapeHtml(a.name) + '</a>'
    ).join('');

    const venueText = [ev.venue, ev.city, ev.country].filter(Boolean).join(' · ');

    card.innerHTML = posterHtml +
      '<div class="card-body">' +
        '<div class="card-date">' + escapeHtml(formatDate(ev.date)) + '</div>' +
        '<div class="card-title"><a href="' + escapeHtml(ev.url || '#') + '" target="_blank" rel="noopener">' + escapeHtml(ev.title || 'Untitled') + '</a></div>' +
        '<div class="card-lineup">' + lineupHtml + '</div>' +
        '<div class="card-venue">' + escapeHtml(venueText) + '</div>' +
      '</div>';

    gridEl.appendChild(card);
  });
}

// Debounced search
let timer;
searchEl.addEventListener('input', () => { clearTimeout(timer); timer = setTimeout(render, 200); });
cityEl.addEventListener('change', render);
countryEl.addEventListener('change', render);
timeEl.addEventListener('change', render);

render();
</script>
</body>
</html>
""")


def load_events(path: str) -> list[dict]:
    with open(path) as f:
        if path.endswith((".yaml", ".yml")):
            return yaml.safe_load(f) or []
        return json.load(f)


def main():
    parser = argparse.ArgumentParser(description="Render Last.fm events as a static HTML page")
    parser.add_argument(
        "input",
        help="Path to events YAML or JSON file (from main.py scraper)",
    )
    parser.add_argument(
        "-o", "--output",
        default="index.html",
        help="Output HTML file (default: index.html)",
    )
    parser.add_argument(
        "--title",
        help="Page title / username (default: inferred from input filename)",
    )
    args = parser.parse_args()

    events = load_events(args.input)
    if not events:
        print("No events found in input file.", file=sys.stderr)
        sys.exit(1)

    # Sort events by date descending (newest first)
    events.sort(key=lambda e: e.get("date", ""), reverse=True)

    # Extract metadata
    dates = [e["date"] for e in events if e.get("date")]
    years = sorted({d[:4] for d in dates})
    min_year = years[0] if years else "?"
    max_year = years[-1] if years else "?"

    # Infer username from filename or --title
    username = args.title
    if not username:
        stem = Path(args.input).stem
        # "mazman159_events" -> "mazman159"
        username = stem.replace("_events", "").replace("-events", "")

    html = HTML_TEMPLATE.render(
        title=f"{username}'s Shows",
        username=username,
        total_events=len(events),
        min_year=min_year,
        max_year=max_year,
        events_json=json.dumps(events, ensure_ascii=False),
    )

    output_path = Path(args.output)
    output_path.write_text(html)
    print(f"Generated {output_path} ({len(events)} events)", file=sys.stderr)


if __name__ == "__main__":
    main()
