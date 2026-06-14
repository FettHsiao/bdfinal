"""Unit tests for PTT crawl helpers."""

from __future__ import annotations

import unittest
from datetime import datetime

from data.collect_ptt_forum_signals import (
    extract_prices,
    is_pricing_question,
    is_recent_enough,
    parse_money_token,
    parse_ptt_datetime,
    resolve_since_date,
)


class PTTDateTests(unittest.TestCase):
    def test_parse_full_ptt_timestamp(self):
        parsed = parse_ptt_datetime("Wed Jul 26 21:06:35 2017")
        self.assertEqual(parsed, datetime(2017, 7, 26, 21, 6, 35))

    def test_recent_filter_excludes_old_posts(self):
        cutoff = resolve_since_date(since_years=2)
        self.assertFalse(is_recent_enough("Wed Jul 26 21:06:35 2017", cutoff))


class PTTPricingTests(unittest.TestCase):
    def test_dot_thousands_format(self):
        self.assertEqual(parse_money_token("28.000"), 28000)
        self.assertIn(28000, extract_prices("每月租金：28.000"))

    def test_comma_and_wan_formats(self):
        self.assertEqual(parse_money_token("28,000"), 28000)
        self.assertEqual(parse_money_token("2.8萬"), 28000)
        self.assertEqual(parse_money_token("2萬8"), 28000)

    def test_pricing_question_requires_question_signal(self):
        self.assertTrue(is_pricing_question("大安區這樣的租金合理嗎？"))
        self.assertFalse(is_pricing_question("大安區出租，月租28000"))


if __name__ == "__main__":
    unittest.main()
