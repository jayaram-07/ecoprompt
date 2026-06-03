"""Unit tests for the in-memory usage guard (rate limit + daily cap).

A fake clock makes the time-based logic deterministic. Run with:
    python -m unittest discover -s tests
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from usage_guard import UsageGuard  # noqa: E402


class FakeClock:
    def __init__(self, start=1_000_000.0):
        self.now = start

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


class PerIpRateLimit(unittest.TestCase):
    def test_blocks_after_limit_within_a_minute(self):
        clock = FakeClock()
        g = UsageGuard(rate_limit_per_minute=3, max_requests_per_day=10_000, clock=clock)
        for _ in range(3):
            self.assertEqual(g.check("1.1.1.1"), (True, None))
        self.assertEqual(g.check("1.1.1.1"), (False, "rate_limit"))

    def test_window_slides_after_60s(self):
        clock = FakeClock()
        g = UsageGuard(rate_limit_per_minute=2, max_requests_per_day=10_000, clock=clock)
        self.assertTrue(g.check("1.1.1.1")[0])
        self.assertTrue(g.check("1.1.1.1")[0])
        self.assertFalse(g.check("1.1.1.1")[0])      # 3rd within the minute -> blocked
        clock.advance(61)
        self.assertTrue(g.check("1.1.1.1")[0])        # window cleared -> allowed again

    def test_different_ips_are_independent(self):
        clock = FakeClock()
        g = UsageGuard(rate_limit_per_minute=1, max_requests_per_day=10_000, clock=clock)
        self.assertTrue(g.check("1.1.1.1")[0])
        self.assertFalse(g.check("1.1.1.1")[0])
        self.assertTrue(g.check("2.2.2.2")[0])        # a different IP is unaffected


class GlobalDailyCap(unittest.TestCase):
    def test_blocks_after_daily_cap_across_ips(self):
        clock = FakeClock()
        g = UsageGuard(rate_limit_per_minute=10_000, max_requests_per_day=4, clock=clock)
        self.assertTrue(g.check("a")[0])
        self.assertTrue(g.check("b")[0])
        self.assertTrue(g.check("c")[0])
        self.assertTrue(g.check("d")[0])
        self.assertEqual(g.check("e"), (False, "daily_cap"))   # 5th request, any IP

    def test_counter_resets_next_day(self):
        clock = FakeClock()
        g = UsageGuard(rate_limit_per_minute=10_000, max_requests_per_day=1, clock=clock)
        self.assertTrue(g.check("a")[0])
        self.assertEqual(g.check("a"), (False, "daily_cap"))
        clock.advance(86_400)                                  # next day
        self.assertTrue(g.check("a")[0])


class Stats(unittest.TestCase):
    def test_stats_report_remaining(self):
        g = UsageGuard(rate_limit_per_minute=100, max_requests_per_day=10)
        g.check("a")
        g.check("a")
        stats = g.stats()
        self.assertEqual(stats["requests_today"], 2)
        self.assertEqual(stats["remaining_today"], 8)
        self.assertEqual(stats["daily_limit"], 10)


if __name__ == "__main__":
    unittest.main()
