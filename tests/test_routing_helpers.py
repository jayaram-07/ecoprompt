"""Unit tests for EcoPrompt's pure routing-decision helpers.

These cover the logic that decides *which tier* answers a prompt and how many
tokens to budget — the core of the energy-efficiency story. They run offline
(no API calls). Run with:  python -m unittest discover -s tests
"""
import os
import sys
import unittest

# Dummy key so `import main` (which constructs a Groq client) succeeds offline.
os.environ.setdefault("GROQ_API_KEY", "test_dummy_key")
# Allow `import main` when tests are run from the repo root.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: E402


class PromptComplexityScore(unittest.TestCase):
    def test_trivial_prompt_scores_zero(self):
        self.assertEqual(main.prompt_complexity_score("hi"), 0)

    def test_short_factual_prompt_is_low(self):
        self.assertLess(main.prompt_complexity_score("what is photosynthesis"), 4)

    def test_long_multiclause_prompt_is_high(self):
        prompt = (
            "Compare and contrast monolithic versus microservices architecture, "
            "because I need a detailed analysis of the tradeoffs"
        )
        self.assertGreaterEqual(main.prompt_complexity_score(prompt), 4)

    def test_realtime_keyword_raises_score(self):
        # "latest"/"today" should push a prompt toward the heavier routes.
        with_realtime = main.prompt_complexity_score("what is the latest news today")
        without = main.prompt_complexity_score("what is the news")
        self.assertGreater(with_realtime, without)


class IsSimplePrompt(unittest.TestCase):
    def test_simple_definitional_prompt(self):
        self.assertTrue(main.is_simple_prompt("what is photosynthesis"))

    def test_complex_prompt_is_not_simple(self):
        self.assertFalse(
            main.is_simple_prompt(
                "Compare and contrast microservices versus monolith in detail"
            )
        )

    def test_long_prompt_is_not_simple(self):
        long_prompt = "explain " + "word " * 20
        self.assertFalse(main.is_simple_prompt(long_prompt))


class SelectMaxTokens(unittest.TestCase):
    def test_code_request_gets_largest_budget(self):
        self.assertEqual(
            main.select_max_tokens("write a python function to sort a list"), 420
        )

    def test_simple_prompt_gets_smallest_budget(self):
        self.assertEqual(main.select_max_tokens("what is photosynthesis"), 120)

    def test_complex_prompt_gets_large_budget(self):
        prompt = (
            "Compare and contrast monolithic versus microservices architecture, "
            "because I need a detailed analysis of the tradeoffs"
        )
        self.assertEqual(main.select_max_tokens(prompt), 400)

    def test_default_budget(self):
        self.assertEqual(main.select_max_tokens("tell me a fun fact about dogs"), 280)


class HostnameHelpers(unittest.TestCase):
    def test_extract_hostname_strips_www_and_lowercases(self):
        self.assertEqual(main.extract_hostname("https://www.BBC.com/news/x"), "bbc.com")

    def test_extract_hostname_handles_bad_url(self):
        self.assertEqual(main.extract_hostname("not a url"), "")

    def test_hostname_matches_exact(self):
        self.assertTrue(main.hostname_matches("bbc.com", "bbc.com"))

    def test_hostname_matches_subdomain(self):
        self.assertTrue(main.hostname_matches("news.bbc.com", "bbc.com"))

    def test_hostname_does_not_match_unrelated(self):
        self.assertFalse(main.hostname_matches("example.com", "bbc.com"))


class EnergyEstimate(unittest.TestCase):
    def test_energy_formula(self):
        # ((ms/1000) * watts) / 3600 / 1000
        self.assertAlmostEqual(
            main.estimate_energy_kwh(1000, 50), (1 * 50) / 3600 / 1000, places=12
        )

    def test_zero_latency_is_zero_energy(self):
        self.assertEqual(main.estimate_energy_kwh(0, 50), 0)


if __name__ == "__main__":
    unittest.main()
