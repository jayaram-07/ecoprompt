"""Unit tests for the knowledge-base tokenizer used by the local KB routes.

The tokenizer normalizes prompts (lowercasing, stopword removal, synonym
folding) so cheap local lookups can match curated knowledge without an LLM.
Run with:  python -m unittest discover -s tests
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kb.kb_utils import tokenize  # noqa: E402


class Tokenize(unittest.TestCase):
    def test_lowercases_and_removes_stopwords(self):
        self.assertEqual(tokenize("What is the capital of France"), ["capital", "france"])

    def test_strips_punctuation(self):
        self.assertEqual(tokenize("Photosynthesis?"), ["photosynthesis"])

    def test_synonym_money_to_currency(self):
        self.assertIn("currency", tokenize("what is the money"))
        self.assertNotIn("money", tokenize("what is the money"))

    def test_synonym_leader_to_president(self):
        self.assertEqual(tokenize("who is the leader of India"), ["president", "india"])

    def test_empty_string_returns_empty_list(self):
        self.assertEqual(tokenize(""), [])


if __name__ == "__main__":
    unittest.main()
