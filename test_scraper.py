#!/usr/bin/env python3
"""Offline tests for NJH parsing."""

import unittest
from datetime import datetime, timezone

from scraper import AQI_DETAIL_URL, URL, parse_njh_aqi_detail, parse_njh_reading

SUMMARY_HTML = """
<html><body>
Current Hour:
<table>
<tr><td>Denver[expand +]</td><td><a href="site_description.aspx#NJH">NJH</a></td>
<td>Moderate</td><td>64</td><td>Particulate &lt; 2.5 micrometers</td>
<td>16 µg/m3</td><td>24-hour</td><td>7 AM</td></tr>
</table>
Daily Highs:
</body></html>
"""

DETAIL_HTML = """
<html><body>
<table>
<tr><td>7:00 AM</td><td>NJH</td><td>PM10</td><td>24</td><td>Good</td><td>33</td><td>36 µg/m3</td></tr>
<tr><td>7:00 AM</td><td>NJH</td><td>PM2.5</td><td>24</td><td>Moderate</td><td>64</td><td>16 µg/m3</td></tr>
<tr><td>6:00 AM</td><td>NJH</td><td>PM2.5</td><td>24</td><td>Moderate</td><td>65</td><td>16 µg/m3</td></tr>
</table>
</body></html>
"""

SCRAPED_AT = datetime(2026, 7, 4, 15, 0, tzinfo=timezone.utc)


class ParseNjhTests(unittest.TestCase):
    def test_parse_summary_row(self) -> None:
        reading = parse_njh_reading(SUMMARY_HTML, scraped_at=SCRAPED_AT)
        self.assertEqual(reading.site, "NJH")
        self.assertEqual(reading.max_aqi, 64)
        self.assertEqual(reading.air_quality, "Moderate")
        self.assertEqual(reading.report_time_mst, "7 AM")
        self.assertEqual(reading.source_url, URL)

    def test_parse_aqi_detail_uses_latest_hour_and_max_aqi(self) -> None:
        reading = parse_njh_aqi_detail(DETAIL_HTML, scraped_at=SCRAPED_AT)
        self.assertEqual(reading.site, "NJH")
        self.assertEqual(reading.area, "Denver")
        self.assertEqual(reading.max_aqi, 64)
        self.assertEqual(reading.pollutant, "PM2.5")
        self.assertEqual(reading.air_quality, "Moderate")
        self.assertEqual(reading.report_time_mst, "7:00 AM")
        self.assertEqual(reading.period, "24-hour")
        self.assertEqual(reading.source_url, AQI_DETAIL_URL)


if __name__ == "__main__":
    unittest.main()
