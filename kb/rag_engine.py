import json
import os
from kb.kb_utils import compute_score


# -----------------------
# Load KB Files
# -----------------------
BASE_PATH = os.path.dirname(__file__)

FILES = [
    "history.json",
    "programming.json",
    "high_level_concepts.json",
    "science_physics.json",
    "science_chemistry.json",
    "science_biology.json",
    "math_definitions.json"
]

RAG_DATA = []

for file_name in FILES:
    path = os.path.join(BASE_PATH, file_name)

    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

            if isinstance(data, list):
                RAG_DATA.extend(data)


# -----------------------
# Improved Scoring
# -----------------------
def score_document(prompt: str, entry: dict):

    score = compute_score(prompt, entry)

    prompt_lower = prompt.lower()
    title = entry.get("title", "").lower()

    # Strong exact title boost
    if title and title in prompt_lower:
        score += 10

    # Keyword boost
    for kw in entry.get("keywords", []):
        if kw.lower() in prompt_lower:
            score += 5

    # Partial title word boost
    for word in title.split():
        if word in prompt_lower:
            score += 2

    return score


# -----------------------
# Retrieve Top K Docs
# -----------------------
def retrieve_top_k(prompt: str, k: int = 3, min_score: int = 5):

    scored = []

    for entry in RAG_DATA:

        score = score_document(prompt, entry)

        if score >= min_score:
            scored.append((entry, score))

    if not scored:
        return []

    # Highest score first
    scored.sort(key=lambda x: x[1], reverse=True)

    # Return only entries
    return [item[0] for item in scored[:k]]