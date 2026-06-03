"""Integration test: the rate limit is actually enforced at the HTTP layer.

Uses FastAPI's TestClient and a deterministic (math) prompt so no external
API is called — the request is answered by the local deterministic engine.
"""
import os
import sys
import unittest

os.environ.setdefault("GROQ_API_KEY", "test_dummy_key")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient  # noqa: E402
import main  # noqa: E402


class EndpointRateLimit(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(main.app)
        # Snapshot and reset guard state for isolation.
        self._orig_rate = main.guard.rate_limit_per_minute
        self._orig_day = main.guard.max_requests_per_day
        main.guard._ip_hits.clear()
        main.guard._day_count = 0

    def tearDown(self):
        main.guard.rate_limit_per_minute = self._orig_rate
        main.guard.max_requests_per_day = self._orig_day
        main.guard._ip_hits.clear()
        main.guard._day_count = 0

    def test_allows_under_limit_then_429s_over_limit(self):
        main.guard.rate_limit_per_minute = 2
        main.guard.max_requests_per_day = 10_000

        # Deterministic prompt -> handled locally, no paid API call.
        body = {"prompt": "what is 2 + 2"}
        r1 = self.client.post("/generate", json=body)
        r2 = self.client.post("/generate", json=body)
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(r1.json()["level_used"], "deterministic")

        # 3rd request within the minute -> blocked.
        r3 = self.client.post("/generate", json=body)
        self.assertEqual(r3.status_code, 429)
        self.assertIn("slow down", r3.json()["detail"].lower())

    def test_daily_cap_returns_friendly_message(self):
        main.guard.rate_limit_per_minute = 10_000
        main.guard.max_requests_per_day = 1

        body = {"prompt": "what is 3 + 5"}
        self.assertEqual(self.client.post("/generate", json=body).status_code, 200)
        blocked = self.client.post("/generate", json=body)
        self.assertEqual(blocked.status_code, 429)
        self.assertIn("tomorrow", blocked.json()["detail"].lower())


if __name__ == "__main__":
    unittest.main()
