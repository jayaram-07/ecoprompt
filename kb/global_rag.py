from kb.math_lookup import MATH_DATA
from kb.science_lookup import SCIENCE_DATA
from kb.history_lookup import HISTORY_DATA
from kb.programming_lookup import PROGRAMMING_DATA
from kb.high_level_lookup import HIGH_LEVEL_DATA

from kb.kb_utils import compute_score


# Combine ALL KB data
ALL_KB_DATA = (
    MATH_DATA +
    SCIENCE_DATA +
    HISTORY_DATA +
    PROGRAMMING_DATA +
    HIGH_LEVEL_DATA
)


MIN_RAG_SCORE = 8


def format_generic(entry: dict):

    title = entry.get("title", "")
    formula = entry.get("formula")
    content = entry.get("content")
    description = entry.get("description")

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


def global_rag_lookup(prompt: str):

    best_entry = None
    best_score = 0

    for entry in ALL_KB_DATA:
        score = compute_score(prompt, entry)

        if score > best_score:
            best_score = score
            best_entry = entry

    # Confidence gate
    if best_score < MIN_RAG_SCORE:
        print("RAG skipped — weak match:", best_score)
        return None, 0

    response = format_generic(best_entry)

    return response, best_score