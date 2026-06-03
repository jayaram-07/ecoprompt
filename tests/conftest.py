"""Test setup: provide a dummy API key so `import main` succeeds without real
credentials. The routing-helper functions under test are pure and never make
network calls, so a placeholder key is sufficient.
"""
import os

os.environ.setdefault("GROQ_API_KEY", "test_dummy_key")
