"""Unified CLI for Last.fm event scraper and renderer."""

import argparse
import sys

from scrape import run_scrape
from render import run_render


def main():
    parser = argparse.ArgumentParser(
        prog="lastfm",
        description="Scrape and visualize Last.fm user events",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # --- scrape ---
    scrape_parser = subparsers.add_parser("scrape", help="Scrape events and download poster images from a Last.fm profile")
    scrape_parser.add_argument(
        "profile_url",
        help="Last.fm profile or events URL, e.g. https://www.last.fm/user/mazman159/events",
    )
    scrape_parser.add_argument(
        "-o", "--output",
        help="Output file path (.yaml/.yml or .json). Poster images are saved to an images/ folder next to this file. Defaults to JSON on stdout (no images).",
    )
    scrape_parser.add_argument(
        "--no-posters", action="store_true",
        help="Skip downloading event poster images.",
    )
    scrape_parser.add_argument(
        "--force-posters", action="store_true",
        help="Re-download all poster images even if they already exist.",
    )

    # --- render ---
    render_parser = subparsers.add_parser("render", help="Render events as a static HTML page")
    render_parser.add_argument(
        "input",
        help="Path to events YAML or JSON file",
    )
    render_parser.add_argument(
        "-o", "--output",
        default="index.html",
        help="Output HTML file (default: index.html)",
    )
    render_parser.add_argument(
        "--title",
        help="Page title / username (default: inferred from input filename)",
    )

    # --- run ---
    run_parser = subparsers.add_parser("run", help="Scrape events, download posters, and render HTML in one step")
    run_parser.add_argument(
        "profile_url",
        help="Last.fm profile or events URL, e.g. https://www.last.fm/user/mazman159/events",
    )
    run_parser.add_argument(
        "-o", "--output",
        help="Events output file path (.yaml/.yml). Poster images are saved to an images/ folder next to this file. Default: <username>_events.yaml",
    )
    run_parser.add_argument(
        "--html", default="index.html",
        help="Output HTML file (default: index.html)",
    )
    run_parser.add_argument(
        "--title",
        help="Page title / username (default: inferred from filename)",
    )
    run_parser.add_argument(
        "--no-posters", action="store_true",
        help="Skip downloading event poster images.",
    )
    run_parser.add_argument(
        "--force-posters", action="store_true",
        help="Re-download all poster images even if they already exist.",
    )

    args = parser.parse_args()

    if args.command == "scrape":
        run_scrape(args.profile_url, args.output, args.no_posters, args.force_posters)

    elif args.command == "render":
        run_render(args.input, args.output, args.title)

    elif args.command == "run":
        # Infer output filename from profile URL if not specified
        output = args.output
        if not output:
            from scrape import parse_profile_url
            username = parse_profile_url(args.profile_url)
            output = f"{username}_events.yaml"

        run_scrape(args.profile_url, output, args.no_posters, args.force_posters)
        run_render(output, args.html, args.title)


if __name__ == "__main__":
    main()
