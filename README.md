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

The LaunchAgent passes `--once` so launchd handles hourly scheduling via `StartInterval`. Do not run `scraper.py` without `--once` under launchd unless you want a long-lived daemon instead.

**Install outside `~/Documents`.** macOS blocks background processes (including launchd) from reading `~/Documents` unless you grant Full Disk Access. Put the project somewhere launchd can reach, e.g.:

```bash
mkdir -p ~/Library/Application\ Support/colorado-njh-aqi
cp -R . ~/Library/Application\ Support/colorado-njh-aqi/
```

Edit paths in `com.local.colorado-njh-aqi.plist` to match that location, then:

```bash
cp com.local.colorado-njh-aqi.plist ~/Library/LaunchAgents/
launchctl bootstrap "gui/$(id -u)" ~/Library/LaunchAgents/com.local.colorado-njh-aqi.plist
```

To reload after changing the plist:

```bash
launchctl bootout "gui/$(id -u)/com.local.colorado-njh-aqi"
cp com.local.colorado-njh-aqi.plist ~/Library/LaunchAgents/
launchctl bootstrap "gui/$(id -u)" ~/Library/LaunchAgents/com.local.colorado-njh-aqi.plist
```

Check status and recent log output:

```bash
launchctl print "gui/$(id -u)/com.local.colorado-njh-aqi" | grep -E "last exit|state"
tail data/scraper.log
```

#### Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `Bootstrap failed: 5: Input/output error` | Job is already loaded | Run `launchctl bootout` first (see reload steps above) |
| `Operation not permitted` in `scraper.log` | Project lives in `~/Documents` | Move to `~/Library/Application Support/` (recommended) or grant Full Disk Access to `/usr/bin/python3` in System Settings → Privacy & Security |
| `last exit code = 2` | Python couldn't run the script (often the Documents permission issue) | Check `data/scraper.log` for the exact error |

## Options

| Flag | Description |
|------|-------------|
| `--once` | Run once and exit |
| `--test-notify` | Send a test ntfy notification |
| `--no-notify` | Disable push notifications |
| `--no-save` | Skip CSV logging |
| `NOTIFY_MIN_AQI` | Only notify when AQI ≥ threshold (in `.env`) |

Requires **Python 3** and **curl**.
