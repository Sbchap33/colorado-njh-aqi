# Colorado NJH AQI Scraper

Hourly scraper for the **NJH** monitoring site Max AQI from [Colorado Air Quality Today](https://www.colorado.gov/airquality/air_quality.aspx), with optional iPhone push notifications via [ntfy](https://ntfy.sh).

## Setup

```bash
cp .env.example .env
# Edit .env and set NTFY_TOPIC to your ntfy subscription topic
```

### iPhone notifications

1. Install the free **ntfy** app from the App Store
2. Subscribe to your topic (e.g. `njh-aqi-samuel-7f3a` — no leading slash)
3. Set `NTFY_TOPIC` in `.env`
4. Test: `python3 scraper.py --test-notify`

## Usage

```bash
# Single scrape
python3 scraper.py --once --json

# Hourly scraper with notifications
python3 scraper.py
```

Readings append to `data/njh_aqi.csv`.

### macOS background job

Edit paths in `com.local.colorado-njh-aqi.plist`, then:

```bash
cp com.local.colorado-njh-aqi.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.local.colorado-njh-aqi.plist
```

## Options

| Flag | Description |
|------|-------------|
| `--once` | Run once and exit |
| `--test-notify` | Send a test ntfy notification |
| `--no-notify` | Disable push notifications |
| `--no-save` | Skip CSV logging |
| `NOTIFY_MIN_AQI` | Only notify when AQI ≥ threshold (in `.env`) |

Requires **Python 3** and **curl**.
