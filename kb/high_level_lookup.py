import json
import os
from kb.kb_utils import compute_score

FILE_PATH = os.path.join(os.path.dirname(__file__), "high_level_concepts.json")

with open(FILE_PATH, "r", encoding="utf-8") as f:
    HIGH_LEVEL_DATA = json.load(f)


def high_level_lookup(prompt: str):
    best_match = None
    best_score = 0

    for entry in HIGH_LEVEL_DATA:
        score = compute_score(prompt, entry)

        if score > best_score:
            best_score = score
            best_match = entry

    if best_score >= 4:
        return format_high_level_response(best_match), best_score

    return None, 0


def format_high_level_response(entry):
    if not entry:
        return None

    title = entry.get("title", "")
    description = entry.get("description", "")

    parts = []

    if title:
        parts.append(title)

    if description:
        parts.append(description)

    return "\n\n".join(parts).strip()