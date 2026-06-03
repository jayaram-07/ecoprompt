import json
import os
from kb.kb_utils import compute_score

# Load history data once
FILE_PATH = os.path.join(os.path.dirname(__file__), "history.json")

with open(FILE_PATH, "r", encoding="utf-8") as f:
    HISTORY_DATA = json.load(f)


def history_lookup(prompt: str):
    best_match = None
    best_score = 0
    prompt_lower = prompt.lower()

    for entry in HISTORY_DATA:
        score = compute_score(prompt, entry)

        title = entry.get("title", "").lower()

        # Strong exact phrase boost
        if title and title in prompt_lower:
            score += 8

        # Extra boost if major keywords appear
        keywords = entry.get("keywords", [])
        for kw in keywords:
            if kw.lower() in prompt_lower:
                score += 5

        if score > best_score:
            best_score = score
            best_match = entry

    # Return BOTH response and score
    if best_score >= 6:
        return format_history_response(best_match), best_score

    return None, 0


def format_history_response(entry):
    if not entry:
        return None

    title = entry.get("title", "")
    year = entry.get("year")
    content = entry.get("content")
    description = entry.get("description")

    parts = []

    if title:
        parts.append(title)

    if year:
        parts.append(f"Year: {year}")

    # Prefer content over description
    if content:
        parts.append(content)
    elif description:
        parts.append(description)

    return "\n\n".join(parts).strip()