"""Lightweight, dependency-free usage guard for the public demo backend.

Protects the billed Gemini / Groq APIs from runaway usage on a public endpoint
with two limits, enforced at the API entrance:

  * per-IP rate limit  — stops one client from spamming requests
  * global daily cap    — bounds total requests/day, capping paid-API exposure

State is in-memory (no Redis/DB). On Cloud Run this means the limits are
enforced *per instance*, so the effective ceiling is roughly
``limit * number_of_instances``. For a strict cap, run with ``--max-instances=1``.
Tune via env vars (see ``guard`` below).
"""
import os
import time
import threading
from collections import deque, defaultdict


class UsageGuard:
    def __init__(self, rate_limit_per_minute=20, max_requests_per_day=500, clock=None):
        self.rate_limit_per_minute = rate_limit_per_minute
        self.max_requests_per_day = max_requests_per_day
        self._clock = clock or time.time
        self._lock = threading.Lock()
        self._ip_hits = defaultdict(deque)   # ip -> deque[timestamps within last 60s]
        self._day = self._current_day()
        self._day_count = 0

    def _current_day(self):
        return int(self._clock() // 86400)

    def check(self, ip):
        """Record a request from ``ip`` and decide if it's allowed.

        Returns ``(allowed: bool, reason: str | None)`` where reason is
        ``"daily_cap"`` or ``"rate_limit"`` when blocked.
        """
        now = self._clock()
        with self._lock:
            # Reset the daily counter (and per-IP windows) when the day rolls over.
            day = self._current_day()
            if day != self._day:
                self._day = day
                self._day_count = 0
                self._ip_hits.clear()

            if self._day_count >= self.max_requests_per_day:
                return False, "daily_cap"

            # Sliding 60-second window per IP.
            hits = self._ip_hits[ip]
            cutoff = now - 60
            while hits and hits[0] < cutoff:
                hits.popleft()
            if len(hits) >= self.rate_limit_per_minute:
                return False, "rate_limit"

            hits.append(now)
            self._day_count += 1
            return True, None

    def stats(self):
        with self._lock:
            return {
                "requests_today": self._day_count,
                "daily_limit": self.max_requests_per_day,
                "remaining_today": max(0, self.max_requests_per_day - self._day_count),
                "rate_limit_per_minute": self.rate_limit_per_minute,
            }


def _env_int(name, default):
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


# Set RATE_LIMIT_ENABLED=0 to disable (e.g. for local dev / load testing).
ENABLED = os.getenv("RATE_LIMIT_ENABLED", "1").lower() not in ("0", "false", "no")

# Default module-level guard, configured from the environment.
guard = UsageGuard(
    rate_limit_per_minute=_env_int("RATE_LIMIT_PER_MINUTE", 20),
    max_requests_per_day=_env_int("MAX_REQUESTS_PER_DAY", 500),
)
