import json
import os
from kb.kb_utils import compute_score

BASE_PATH = os.path.dirname(__file__)

FILES = [
    "science_physics.json",
    "science_chemistry.json",
    "science_biology.json"
]

SCIENCE_DATA = []

for file_name in FILES:
    path = os.path.join(BASE_PATH, file_name)
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
        SCIENCE_DATA.extend(data)


def science_lookup(prompt: str):
    best_match = None
    best_score = 0

    for entry in SCIENCE_DATA:
        score = compute_score(prompt, entry)

        if score > best_score:
            best_score = score
            best_match = entry

    # 🔥 Return BOTH response and score
    if best_score >= 4:
        return format_science_response(best_match), best_score

    return None, 0


def format_science_response(entry: dict):
    if not entry:
        return None

    title = entry.get("title", "")
    content = entry.get("content")
    description = entry.get("description")
    formula = entry.get("formula")

    parts = []

    if title:
        parts.append(title)

    if formula:
        parts.append(f"Formula:\n{formula}")

    if content:
        parts.append(content)
    elif description:
        parts.append(description)

    return "\n\n".join(parts).strip()