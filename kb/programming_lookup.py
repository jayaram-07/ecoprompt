import json
import os
from kb.kb_utils import compute_score

FILE_PATH = os.path.join(os.path.dirname(__file__), "programming.json")

with open(FILE_PATH, "r", encoding="utf-8") as f:
    PROGRAMMING_DATA = json.load(f)


def programming_lookup(prompt: str):
    best_match = None
    best_score = 0

    for entry in PROGRAMMING_DATA:
        score = compute_score(prompt, entry)

        if score > best_score:
            best_score = score
            best_match = entry

    if best_score >= 4:
        return format_programming_response(best_match), best_score

    return None, 0


def format_programming_response(entry: dict):
    if not entry:
        return None

    title = entry.get("title", "")
    content = entry.get("content")

    parts = []

    if title:
        parts.append(title)

    if content:
        parts.append(content)

    return "\n\n".join(parts).strip()