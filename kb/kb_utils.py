import re

# Common words we ignore during scoring
STOPWORDS = {
    "what", "is", "the", "of", "in", "a", "an", "define",
    "explain", "about", "tell", "me", "who", "when",
    "where", "how", "does", "do", "did", "use", "uses"
}

# Lightweight synonym normalization
SYNONYMS = {
    "money": "currency",
    "cash": "currency",
    "capitalcity": "capital",
    "leader": "president",
    "law": "formula",
    "equation": "formula",
    "rule": "law"
}


def tokenize(text: str):
    text = text.lower()
    words = re.findall(r'\b\w+\b', text)

    # Remove stopwords
    filtered = [w for w in words if w not in STOPWORDS]

    # Normalize synonyms
    normalized = []
    for word in filtered:
        if word in SYNONYMS:
            normalized.append(SYNONYMS[word])
        else:
            normalized.append(word)

    return normalized


def compute_score(prompt: str, entry: dict):
    prompt_tokens = set(tokenize(prompt))

    title_text = entry.get("title", "")
    keyword_text = " ".join(entry.get("keywords", []))
    description_text = entry.get("description", "")
    content_text = entry.get("content", "")
    formula_text = entry.get("formula", "")

    combined_text = f"{title_text} {keyword_text} {description_text} {content_text} {formula_text}"
    entry_tokens = set(tokenize(combined_text))

    overlap = prompt_tokens & entry_tokens

    score = 0

    # Strong weight for rare overlap
    for token in overlap:
        if len(token) > 5:
            score += 5
        else:
            score += 2

    # Exact title bonus
    if title_text.lower() in prompt.lower():
        score += 10

    return score