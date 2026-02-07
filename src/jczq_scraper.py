#!/usr/bin/env python3
"""Scrape JCZQ football match data from NetEase sports page."""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import requests
from bs4 import BeautifulSoup

DEFAULT_URL = "https://sports.163.com/caipiao/match/football/jczq"


@dataclass
class MatchRecord:
    """Normalized representation of a match row."""

    fields: dict[str, Any]


class ScrapeError(RuntimeError):
    """Raised when the scraper cannot parse match data."""


def build_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/119.0 Safari/537.36"
            ),
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }
    )
    return session


def fetch_html(url: str, timeout: int = 20) -> str:
    session = build_session()
    logging.info("Fetching %s", url)
    response = session.get(url, timeout=timeout)
    response.raise_for_status()
    return response.text


def extract_table_matches(soup: BeautifulSoup) -> list[MatchRecord]:
    matches: list[MatchRecord] = []
    for row in soup.select("table tr"):
        if not row.find_all("td"):
            continue
        cells = [cell.get_text(strip=True) for cell in row.find_all("td")]
        if len(cells) < 3:
            continue
        fields = {f"col_{idx}": value for idx, value in enumerate(cells, start=1)}
        for attr, value in row.attrs.items():
            if attr.startswith("data-"):
                fields[attr] = value
        matches.append(MatchRecord(fields=fields))
    return matches


def extract_json_matches(html: str) -> list[MatchRecord]:
    matches: list[MatchRecord] = []
    patterns = [
        r"window\.__DATA__\s*=\s*(\{.*?\})\s*;",
        r"window\.__NUXT__\s*=\s*(\{.*?\})\s*;",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, html, re.DOTALL):
            try:
                payload = json.loads(match.group(1))
            except json.JSONDecodeError:
                continue
            matches.extend(normalize_payload(payload))
    return matches


def normalize_payload(payload: Any) -> list[MatchRecord]:
    matches: list[MatchRecord] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            if isinstance(value, (dict, list)):
                matches.extend(normalize_payload(value))
            if key.lower() in {"matchlist", "matches", "match"} and isinstance(
                value, list
            ):
                for item in value:
                    if isinstance(item, dict):
                        matches.append(MatchRecord(fields=item))
    elif isinstance(payload, list):
        for item in payload:
            matches.extend(normalize_payload(item))
    return matches


def parse_matches(html: str) -> list[MatchRecord]:
    soup = BeautifulSoup(html, "html.parser")
    matches = extract_table_matches(soup)
    if matches:
        return matches
    matches = extract_json_matches(html)
    if matches:
        return matches
    raise ScrapeError("No match data found; page structure may have changed.")


def write_output(records: Iterable[MatchRecord], output: Path) -> None:
    data = [record.fields for record in records]
    output.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=DEFAULT_URL, help="Match page URL")
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("jczq_matches.json"),
        help="Output JSON path",
    )
    parser.add_argument(
        "--raw-html",
        type=Path,
        help="Optional path to save raw HTML for debugging",
    )
    parser.add_argument("--timeout", type=int, default=20, help="Request timeout")
    parser.add_argument("--verbose", action="store_true", help="Enable debug logs")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )
    try:
        html = fetch_html(args.url, timeout=args.timeout)
    except requests.RequestException as exc:
        logging.error("Failed to fetch page: %s", exc)
        return 1

    if args.raw_html:
        args.raw_html.write_text(html, encoding="utf-8")
        logging.info("Saved raw HTML to %s", args.raw_html)

    try:
        matches = parse_matches(html)
    except ScrapeError as exc:
        logging.error("%s", exc)
        return 2

    write_output(matches, args.out)
    logging.info("Wrote %d match records to %s", len(matches), args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
