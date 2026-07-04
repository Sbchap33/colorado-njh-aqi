#!/usr/bin/env python3
"""Send NJH AQI readings to iPhone via ntfy push notifications."""

from __future__ import annotations

import logging
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional
from urllib.parse import quote

DEFAULT_NTFY_SERVER = "https://ntfy.sh"
ENV_FILE = Path(__file__).resolve().parent / ".env"


@dataclass(frozen=True)
class NotifyConfig:
    topic: str
    server: str = DEFAULT_NTFY_SERVER
    token: Optional[str] = None
    min_aqi: int = 0

    @classmethod
    def from_env(cls, env_path: Optional[Path] = None) -> Optional["NotifyConfig"]:
        _load_env_file(env_path or ENV_FILE)

        topic = os.environ.get("NTFY_TOPIC", "").strip()
        if not topic:
            return None

        min_aqi_text = os.environ.get("NOTIFY_MIN_AQI", "0").strip()
        try:
            min_aqi = int(min_aqi_text)
        except ValueError as exc:
            raise ValueError(f"NOTIFY_MIN_AQI must be an integer, got {min_aqi_text!r}") from exc

        token = os.environ.get("NTFY_TOKEN", "").strip() or None
        server = os.environ.get("NTFY_SERVER", DEFAULT_NTFY_SERVER).strip().rstrip("/")

        return cls(topic=topic, server=server, token=token, min_aqi=min_aqi)


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return

    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'\"")
        os.environ.setdefault(key, value)


def _aqi_priority(max_aqi: int) -> str:
    if max_aqi >= 151:
        return "urgent"
    if max_aqi >= 101:
        return "high"
    if max_aqi >= 51:
        return "default"
    return "low"


def _aqi_tag(max_aqi: int) -> str:
    if max_aqi >= 201:
        return "skull"
    if max_aqi >= 151:
        return "rotating_light"
    if max_aqi >= 101:
        return "warning"
    if max_aqi >= 51:
        return "partly_sunny"
    return "sunny"


def format_notification(reading) -> tuple:
    title = f"NJH AQI: {reading.max_aqi} ({reading.air_quality})"
    message = (
        f"{reading.pollutant}\n"
        f"{reading.concentration} ({reading.period})\n"
        f"Report time: {reading.report_time_mst or 'n/a'} MST"
    )
    return title, message


def should_notify(reading, config: NotifyConfig) -> bool:
    return reading.max_aqi >= config.min_aqi


def send_notification(reading, config: NotifyConfig, timeout: int = 30) -> None:
    if not should_notify(reading, config):
        logging.info(
            "Skipping notification: AQI %s is below threshold %s",
            reading.max_aqi,
            config.min_aqi,
        )
        return

    title, message = format_notification(reading)
    topic_url = f"{config.server}/{quote(config.topic, safe='')}"

    command: List[str] = [
        "curl",
        "-fsS",
        "--max-time",
        str(timeout),
        "-d",
        message,
        "-H",
        f"Title: {title}",
        "-H",
        f"Priority: {_aqi_priority(reading.max_aqi)}",
        "-H",
        f"Tags: {_aqi_tag(reading.max_aqi)}",
    ]

    if config.token:
        command.extend(["-H", f"Authorization: Bearer {config.token}"])

    command.append(topic_url)

    subprocess.run(command, check=True, capture_output=True)
    logging.info("Sent iPhone notification to ntfy topic %r", config.topic)


def send_test_notification(config: NotifyConfig) -> None:
    class _Reading:
        max_aqi = 64
        air_quality = "Moderate"
        pollutant = "Particulate < 2.5 micrometers"
        concentration = "16 µg/m3"
        period = "24-hour"
        report_time_mst = "7 AM"

    send_notification(_Reading(), config)
