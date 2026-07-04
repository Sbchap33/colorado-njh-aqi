#!/usr/bin/env python3
"""Scrape Max AQI for the NJH monitoring site from Colorado air quality page."""

from __future__ import annotations

import argparse
import csv
import json
import logging
import re
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from html import unescape
from pathlib import Path
from typing import List, Optional

from notify import NotifyConfig, send_notification

URL = "https://www.colorado.gov/airquality/air_quality.aspx"
SITE_CODE = "NJH"
USER_AGENT = "colorado-njh-aqi-scraper/1.0 (+local monitoring)"
DEFAULT_OUTPUT = Path(__file__).resolve().parent / "data" / "njh_aqi.csv"


@dataclass(frozen=True)
class NjhReading:
    scraped_at: str
    site: str
    area: str
    air_quality: str
    max_aqi: int
    pollutant: str
    concentration: str
    period: str
    report_time_mst: Optional[str]
    source_url: str


def fetch_page(url: str = URL, timeout: int = 30) -> str:
    result = subprocess.run(
        ["curl", "-fsSL", "--max-time", str(timeout), "-A", USER_AGENT, url],
        check=True,
        capture_output=True,
    )
    return result.stdout.decode("utf-8", errors="replace")


def _clean_cell(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text)
    text = unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _extract_current_hour_section(html: str) -> str:
    current_start = html.find("Current Hour:")
    if current_start == -1:
        raise ValueError("Could not find 'Current Hour:' section on page")

    daily_start = html.find("Daily Highs:", current_start)
    if daily_start == -1:
        return html[current_start:]
    return html[current_start:daily_start]


def parse_njh_reading(html: str, scraped_at: Optional[datetime] = None) -> NjhReading:
    section = _extract_current_hour_section(html)
    row_pattern = re.compile(r"<tr[^>]*>(.*?)</tr>", re.IGNORECASE | re.DOTALL)
    site_link = re.compile(
        rf'site_description\.aspx#{SITE_CODE}">{SITE_CODE}</a>',
        re.IGNORECASE,
    )

    match = None
    for row_match in row_pattern.finditer(section):
        if site_link.search(row_match.group(1)):
            match = row_match
            break

    if not match:
        raise ValueError(f"Could not find {SITE_CODE} row in Current Hour table")

    cells = re.findall(r"<td[^>]*>(.*?)</td>", match.group(1), re.DOTALL | re.IGNORECASE)
    if len(cells) < 7:
        raise ValueError(f"Unexpected table structure for {SITE_CODE}: {len(cells)} cells")

    area = re.sub(r"\[expand\s*\+\s*\]", "", _clean_cell(cells[0])).strip()
    site = _clean_cell(cells[1])
    air_quality = _clean_cell(cells[2])
    max_aqi_text = _clean_cell(cells[3])
    pollutant = _clean_cell(cells[4])
    concentration = _clean_cell(cells[5])
    period = _clean_cell(cells[6])
    report_time_mst = _clean_cell(cells[7]) if len(cells) > 7 else None

    if site != SITE_CODE:
        raise ValueError(f"Expected site {SITE_CODE}, found {site!r}")

    try:
        max_aqi = int(max_aqi_text)
    except ValueError as exc:
        raise ValueError(f"Could not parse Max AQI value: {max_aqi_text!r}") from exc

    timestamp = scraped_at or datetime.now(timezone.utc)
    return NjhReading(
        scraped_at=timestamp.isoformat(),
        site=site,
        area=area,
        air_quality=air_quality,
        max_aqi=max_aqi,
        pollutant=pollutant,
        concentration=concentration,
        period=period,
        report_time_mst=report_time_mst,
        source_url=URL,
    )


def scrape_njh_aqi() -> NjhReading:
    html = fetch_page()
    return parse_njh_reading(html)


def append_csv(reading: NjhReading, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    file_exists = output_path.exists()
    with output_path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(asdict(reading).keys()))
        if not file_exists:
            writer.writeheader()
        writer.writerow(asdict(reading))


def log_reading(reading: NjhReading, output_path: Optional[Path]) -> None:
    logging.info(
        "NJH Max AQI: %s (%s) | %s | %s | report time: %s",
        reading.max_aqi,
        reading.air_quality,
        reading.pollutant,
        reading.concentration,
        reading.report_time_mst or "n/a",
    )
    if output_path is not None:
        append_csv(reading, output_path)


def run_once(output_path: Optional[Path], notify_config: Optional[NotifyConfig] = None) -> NjhReading:
    reading = scrape_njh_aqi()
    log_reading(reading, output_path)
    if notify_config is not None:
        try:
            send_notification(reading, notify_config)
        except (subprocess.CalledProcessError, OSError) as exc:
            logging.exception("Notification failed: %s", exc)
    return reading


def seconds_until_next_hour() -> float:
    now = datetime.now()
    next_hour = (now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1))
    return max((next_hour - now).total_seconds(), 0.0)


def run_hourly(
    output_path: Optional[Path],
    align_to_hour: bool,
    notify_config: Optional[NotifyConfig] = None,
) -> None:
    if align_to_hour:
        wait_seconds = seconds_until_next_hour()
        logging.info("Waiting %.0f seconds until next hour", wait_seconds)
        time.sleep(wait_seconds)

    while True:
        try:
            run_once(output_path, notify_config=notify_config)
        except (subprocess.CalledProcessError, ValueError, OSError) as exc:
            logging.exception("Scrape failed: %s", exc)

        if align_to_hour:
            time.sleep(seconds_until_next_hour())
        else:
            time.sleep(3600)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Scrape Max AQI for the NJH site from Colorado air quality data."
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run a single scrape and exit (default: run hourly).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the reading as JSON to stdout (useful with --once).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"CSV file for readings (default: {DEFAULT_OUTPUT}).",
    )
    parser.add_argument(
        "--no-save",
        action="store_true",
        help="Do not append readings to the CSV output file.",
    )
    parser.add_argument(
        "--no-align",
        action="store_true",
        help="Run every 3600 seconds from start instead of aligning to clock hours.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable debug logging.",
    )
    parser.add_argument(
        "--notify",
        action="store_true",
        help="Send iPhone push notification via ntfy (also enabled when NTFY_TOPIC is set).",
    )
    parser.add_argument(
        "--no-notify",
        action="store_true",
        help="Disable notifications even if NTFY_TOPIC is configured.",
    )
    parser.add_argument(
        "--test-notify",
        action="store_true",
        help="Send a test notification and exit.",
    )
    return parser


def resolve_notify_config(args) -> Optional[NotifyConfig]:
    if args.no_notify:
        return None

    config = NotifyConfig.from_env()
    if config is None:
        if args.notify or args.test_notify:
            raise ValueError(
                "Notifications requested but NTFY_TOPIC is not set. "
                "Copy .env.example to .env and set your topic."
            )
        return None

    return config


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    output_path = None if args.no_save else args.output

    try:
        notify_config = resolve_notify_config(args)

        if args.test_notify:
            if notify_config is None:
                notify_config = NotifyConfig.from_env()
            if notify_config is None:
                raise ValueError("Set NTFY_TOPIC in .env before running --test-notify.")
            from notify import send_test_notification

            send_test_notification(notify_config)
            logging.info("Test notification sent")
            return 0

        if args.once:
            reading = run_once(output_path, notify_config=notify_config)
            if args.json:
                print(json.dumps(asdict(reading), indent=2))
            return 0

        logging.info("Starting hourly NJH AQI scraper")
        if notify_config is not None:
            logging.info("iPhone notifications enabled (ntfy topic: %s)", notify_config.topic)
        run_hourly(output_path, align_to_hour=not args.no_align, notify_config=notify_config)
        return 0
    except KeyboardInterrupt:
        logging.info("Stopped by user")
        return 0
    except (subprocess.CalledProcessError, ValueError, OSError) as exc:
        logging.error("Scrape failed: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
