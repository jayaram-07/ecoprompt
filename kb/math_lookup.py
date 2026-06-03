import json
import os
from kb.kb_utils import compute_score

FILE_PATH = os.path.join(os.path.dirname(__file__), "math_definitions.json")

with open(FILE_PATH, "r", encoding="utf-8") as f:
    MATH_DATA = json.load(f)


def math_lookup(prompt: str):
    best_match = None
    best_score = 0

    for entry in MATH_DATA:
        score = compute_score(prompt, entry)

        if score > best_score:
            best_score = score
            best_match = entry

    if best_score >= 4:   # threshold unchanged
        return format_math_response(best_match), best_score

    return None, 0


def format_math_response(entry: dict):
    if not entry:
        return None

    title = entry.get("title", "")
    formula = entry.get("formula")
    description = entry.get("description", "")

    parts = []

    if title:
        parts.append(title)

    if formula:
        parts.append(f"Formula:\n{formula}")

    if description:
        parts.append(description)

    return "\n\n".join(parts).strip()