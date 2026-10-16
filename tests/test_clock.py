import copy
import json
import tempfile
import threading
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

import clock_format
import config_manager
import taskbar_clock
from timezone_utils import get_current_time_in_tz


class TimezoneTests(unittest.TestCase):
    def test_beijing_crosses_date_without_changing_us_timezone(self):
        utc = datetime(2026, 10, 15, 20, 5, tzinfo=timezone.utc)
        with patch("timezone_utils.datetime") as clock:
            clock.now.return_value = utc
            beijing = get_current_time_in_tz("Asia/Shanghai")
            pacific = get_current_time_in_tz("America/Los_Angeles")
        self.assertEqual(beijing.isoformat(), "2026-10-16T04:05:00+08:00")
        self.assertEqual(pacific.isoformat(), "2026-10-15T13:05:00-07:00")

    def test_beijing_stays_utc8_across_us_dst_transition(self):
        values = []
        for month in (7, 12):
            utc = datetime(2026, month, 15, 12, tzinfo=timezone.utc)
            values.append(utc.astimezone(ZoneInfo("America/Los_Angeles")).utcoffset().total_seconds())
            self.assertEqual(utc.astimezone(ZoneInfo("Asia/Shanghai")).hour, 20)
        self.assertEqual(values, [-7 * 3600, -8 * 3600])


class FormatTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 16, 13, 5, 9, tzinfo=ZoneInfo("Asia/Shanghai"))

    def test_windows_receives_target_time_and_keeps_regional_order(self):
        with patch("clock_format._windows_format", side_effect=["1:05 PM", "10/16/2026"]) as native:
            result = clock_format.format_clock(self.now, {"format_style": "windows"}, "zh")
        self.assertEqual(result, ("1:05 PM", "10/16/2026"))
        self.assertEqual(native.call_args_list[0].args[0], self.now)
        self.assertEqual(native.call_args_list[1].kwargs, {"date": True})

    def test_native_failure_still_displays_beijing_date(self):
        with patch("clock_format._windows_format", side_effect=OSError("unavailable")):
            self.assertEqual(clock_format.format_clock(self.now, {}), ("13:05", "2026/10/16"))

    def test_custom_format_and_chinese_period_are_preserved(self):
        config = {"format_style": "custom", "time_format": "%I:%M:%S %p", "date_format": "%d-%m-%Y"}
        self.assertEqual(clock_format.format_clock(self.now, config, "zh"), ("01:05:09 下午", "16-10-2026"))
        self.assertEqual(clock_format.format_clock(self.now, config, "en"), ("01:05:09 PM", "16-10-2026"))

    def test_native_api_accepts_target_systemtime(self):
        text, date = clock_format.format_clock(self.now, {"format_style": "windows"})
        self.assertTrue(text)
        self.assertIn("2026", date)
        self.assertIn("16", date)


class ConfigTests(unittest.TestCase):
    def load(self, value=None):
        with tempfile.TemporaryDirectory() as directory:
            filename = Path(directory) / "config.json"
            if value is not None:
                filename.write_text(json.dumps(value), encoding="utf-8")
            with patch.object(config_manager, "CONFIG_FILE", str(filename)):
                return config_manager.load_config()

    def test_new_install_is_beijing_native_style(self):
        config = self.load()
        self.assertEqual(config["language"], "zh")
        self.assertEqual(config["clocks"][0]["target_timezone"], "Asia/Shanghai")
        self.assertEqual(config["clocks"][0]["format_style"], "windows")
        self.assertEqual(config["clocks"][0]["font_family"], "Segoe UI")

    def test_only_legacy_default_combination_is_migrated(self):
        legacy = {"target_timezone": "Asia/Hong_Kong", "font_family": "Microsoft JhengHei UI",
                  "time_format": "%#I:%M %p", "date_format": "%#d/%#m/%Y",
                  "font_color": "#123456", "font_size": 11}
        original = copy.deepcopy(legacy)
        result = self.load({"clocks": [legacy]})["clocks"][0]
        self.assertEqual(result["target_timezone"], "Asia/Shanghai")
        self.assertEqual(result["format_style"], "windows")
        self.assertEqual(result["font_color"], "#123456")
        self.assertEqual(result["font_size"], 11)
        self.assertEqual(legacy, original)

    def test_beijing_with_legacy_default_style_is_also_migrated(self):
        clock = {"target_timezone": "Asia/Shanghai", "font_family": "Microsoft JhengHei UI",
                 "time_format": "%#I:%M %p", "date_format": "%#d/%#m/%Y"}
        result = self.load({"clocks": [clock]})["clocks"][0]
        self.assertEqual(result["target_timezone"], "Asia/Shanghai")
        self.assertEqual(result["format_style"], "windows")
        self.assertEqual(result["font_family"], "Segoe UI")

    def test_style_migration_does_not_change_custom_timezone(self):
        clock = {"target_timezone": "America/New_York", "font_family": "Microsoft JhengHei UI",
                 "time_format": "%#I:%M %p", "date_format": "%#d/%#m/%Y"}
        result = self.load({"clocks": [clock]})["clocks"][0]
        self.assertEqual(result["target_timezone"], "America/New_York")
        self.assertEqual(result["format_style"], "windows")

    def test_existing_custom_clock_is_preserved(self):
        clock = {"target_timezone": "America/New_York", "font_family": "Arial",
                 "time_format": "%H:%M:%S", "date_format": "%d.%m.%Y", "show_date": False}
        result = self.load({"clocks": [clock]})["clocks"][0]
        self.assertEqual(result["format_style"], "custom")
        for key, value in clock.items():
            self.assertEqual(result[key], value)

    def test_explicit_custom_style_does_not_migrate(self):
        clock = {"target_timezone": "Asia/Hong_Kong", "font_family": "Microsoft JhengHei UI",
                 "time_format": "%#I:%M %p", "date_format": "%#d/%#m/%Y", "format_style": "custom"}
        result = self.load({"clocks": [clock]})["clocks"][0]
        self.assertEqual(result["target_timezone"], "Asia/Hong_Kong")
        self.assertEqual(result["format_style"], "custom")

    def test_empty_clock_list_recovers_default(self):
        self.assertEqual(self.load({"clocks": []})["clocks"][0]["target_timezone"], "Asia/Shanghai")


class TaskbarQueryTests(unittest.TestCase):
    def test_slow_uia_query_never_blocks_ui_thread(self):
        entered, release = threading.Event(), threading.Event()
        def slow_query(hwnd):
            entered.set()
            release.wait(3)
            return (10, 20, 90, 80)
        with taskbar_clock._cache_lock:
            taskbar_clock._clock_cache.clear()
        with patch.object(taskbar_clock, "_query_modern_clock_rect", side_effect=slow_query) as query:
            try:
                start = time.monotonic()
                self.assertIsNone(taskbar_clock.find_modern_clock_rect(123))
                self.assertLess(time.monotonic() - start, .25)
                self.assertTrue(entered.wait(1))
                for _ in range(10):
                    self.assertIsNone(taskbar_clock.find_modern_clock_rect(123))
                self.assertEqual(query.call_count, 1)
            finally:
                release.set()
                for worker in threading.enumerate():
                    if worker.name == "taskbar-clock-query":
                        worker.join(2)
            self.assertEqual(taskbar_clock.find_modern_clock_rect(123), (10, 20, 90, 80))


if __name__ == "__main__":
    unittest.main()
