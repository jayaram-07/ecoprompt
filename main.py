from deterministic import deterministic_engine
from kb.geography_lookup import geography_lookup
from kb.math_lookup import math_lookup
from kb.science_lookup import science_lookup
from kb.history_lookup import history_lookup
from kb.programming_lookup import programming_lookup
from kb.high_level_lookup import high_level_lookup
from kb.rag_engine import retrieve_top_k
from kb.kb_utils import tokenize
from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel
from groq import Groq
from usage_guard import guard, ENABLED as RATE_LIMIT_ENABLED
import os
import re
import requests
from dotenv import load_dotenv
import time
import json
from datetime import datetime
from urllib.parse import urlparse
load_dotenv()
app = FastAPI()


def _client_ip(http_request: Request) -> str:
    """Real client IP, accounting for Cloud Run's proxy (X-Forwarded-For)."""
    forwarded = http_request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return http_request.client.host if http_request.client else "unknown"


def _enforce_limit(http_request: Request) -> None:
    """Raise HTTP 429 if the caller has exceeded the rate or daily limit."""
    if not RATE_LIMIT_ENABLED:
        return
    allowed, reason = guard.check(_client_ip(http_request))
    if not allowed:
        if reason == "daily_cap":
            raise HTTPException(
                status_code=429,
                detail="Daily demo limit reached. Please try again tomorrow.",
            )
        raise HTTPException(
            status_code=429,
            detail="Too many requests — please slow down and try again shortly.",
        )
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Route", "X-Sources"]
)
client = Groq(
    api_key=os.getenv("GROQ_API_KEY")
)
TEMPLATE_PATH = os.path.join("kb", "code_templates.json")
with open(TEMPLATE_PATH, "r") as f:
    CODE_TEMPLATES = json.load(f)
class Message(BaseModel):
    role: str
    content: str
class PromptRequest(BaseModel):
    prompt: str
    history: list[Message] = []
    web_search: bool = False
metrics = {
    "total_prompts": 0,
    "total_latency": 0,
    "total_energy_kwh": 0,
    "route_counts": {
        "deterministic": 0,
        "kb_reasoned_local": 0,
        "rag_local": 0,
        "template_engine": 0,
        "web": 0,
        "local": 0,
        "groq": 0,
        "rejected": 0
    },
    "route_totals": {
        "deterministic": {"count": 0, "latency_ms": 0, "energy_kwh": 0, "estimated_cost_usd": 0},
        "kb_reasoned_local": {"count": 0, "latency_ms": 0, "energy_kwh": 0, "estimated_cost_usd": 0},
        "rag_local": {"count": 0, "latency_ms": 0, "energy_kwh": 0, "estimated_cost_usd": 0},
        "template_engine": {"count": 0, "latency_ms": 0, "energy_kwh": 0, "estimated_cost_usd": 0},
        "web": {"count": 0, "latency_ms": 0, "energy_kwh": 0, "estimated_cost_usd": 0},
        "local": {"count": 0, "latency_ms": 0, "energy_kwh": 0, "estimated_cost_usd": 0},
        "groq": {"count": 0, "latency_ms": 0, "energy_kwh": 0, "estimated_cost_usd": 0},
        "rejected": {"count": 0, "latency_ms": 0, "energy_kwh": 0, "estimated_cost_usd": 0}
    },
    "history": []
}
COST_GPT4O_BASELINE = 0.004  # Avg $4.00 per 1M tokens (GPT-4o)
COST_GROQ_ACTUAL = 0.0007    # Avg $0.70 per 1M tokens (Groq Llama 3 70B)
ELECTRICITY_COST_INR_PER_KWH = 8.0  # Avg cost in India (₹8.00 per kWh)
ESTIMATED_ROUTE_COST_USD = {
    "deterministic": 0.0,
    "kb_reasoned_local": 0.0,
    "rag_local": 0.0,
    "template_engine": 0.0,
    "web": 0.0,
    "local": 0.0,
    "groq": COST_GROQ_ACTUAL,
    "rejected": 0.0,
}
OLLAMA_API_URL = "https://api.groq.com/openai/v1/chat/completions"
LOCAL_MODEL_NAME = "llama-3.1-8b-instant"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GENERIC_TRUSTED_DOMAINS = (
    "reuters.com",
    "apnews.com",
    "bbc.com",
    "theguardian.com",
    "nytimes.com",
    "forbes.com",
    "bloomberg.com",
    "wikipedia.org",
    "britannica.com",
)
BLOCKED_SOURCE_DOMAINS = (
    "youtube.com",
    "youtu.be",
    "reddit.com",
    "quora.com",
    "tiktok.com",
    "instagram.com",
    "facebook.com",
    "sling.com",
    "lunar.app",
    "famousbirthdays.com",
    "witchesofthecraft.com",
    "zodiacsign.com",
)
TOPIC_PREFERRED_DOMAINS = {
    "sports": (
        "premierleague.com",
        "thefa.com",
        "fifa.com",
        "uefa.com",
        "espn.com",
        "bbc.com",
        "skysports.com",
        "tntsports.co.uk",
    ),
    "finance": (
        "coinmarketcap.com",
        "coinbase.com",
        "kraken.com",
        "coingecko.com",
        "moneycontrol.com",
        "xe.com",
        "investing.com",
        "reuters.com",
        "bloomberg.com",
    ),
    "education": (
        ".edu",
        ".ac.in",
        ".gov.in",
        "cbse.gov.in",
        "cambridgeinternational.org",
        "cisce.org",
    ),
}
def record_history(route, latency_ms, energy_kwh):
    metrics["history"].append({
        "timestamp": time.time(),
        "latency_ms": latency_ms,
        "energy_kwh": energy_kwh,
        "route": route
    })
    metrics["history"] = metrics["history"][-100:]
def update_route_metrics(route, latency_ms, energy_kwh):
    metrics["total_prompts"] += 1
    metrics["total_latency"] += latency_ms
    metrics["total_energy_kwh"] += energy_kwh
    metrics["route_counts"][route] += 1
    route_totals = metrics["route_totals"][route]
    route_totals["count"] += 1
    route_totals["latency_ms"] += latency_ms
    route_totals["energy_kwh"] += energy_kwh
    route_totals["estimated_cost_usd"] += ESTIMATED_ROUTE_COST_USD.get(route, 0)
def finalize_stream_metrics(route, start_time, watts):
    latency_ms = round((time.time() - start_time) * 1000, 2)
    energy_kwh = estimate_energy_kwh(latency_ms, watts)
    update_route_metrics(route, latency_ms, energy_kwh)
    record_history(route, latency_ms, energy_kwh)
COMPLEX_KEYWORDS = [
    "analyze",
    "analysis",
    "compare",
    "comparison",
    "prove",
    "justify",
    "evaluate",
    "tradeoff",
    "trade-off",
    "architecture",
    "design",
    "distributed system",
    "machine learning",
    "neural network",
    "optimization",
    "algorithm",
    "blockchain",
    "quantum computing",
    "formal proof",
    "research paper",
    "system design",
    "multi-step",
    "step by step",
    "critique",
    "reason about",
    "essay",
    "detailed",
    "analysis",
    "comprehensive",
    "report",
    "10-page",
    "long-form",
    "news",
    "today",
    "current",
    "latest",
    "recent",
    "2024",
    "2025",
    "2026",
    "price of",
]
SYSTEM_DESIGN_KEYWORDS = {
    "architecture",
    "workflow",
    "rollback",
    "failure",
    "fault",
    "tolerant",
    "approval",
    "operational",
    "complexity",
    "tradeoff",
    "tradeoffs",
    "platform",
    "distributed",
    "event",
    "region",
    "company",
}
EXPLICIT_CODE_REQUEST_TERMS = [
    "write code",
    "give code",
    "show code",
    "generate code",
    "provide code",
    "python code",
    "javascript code",
    "java code",
    "c++ code",
    "code snippet",
    "sample code",
    "example code",
    "implement",
    "write a function",
    "write a program",
    "write a script",
    "function for",
    "code for",
    "snippet for",
    "how to implement",
    "how to write",
    "python function",
    "javascript function",
    "show me a function",
    "with code",
    "in code",
    "program this",
    "pseudocode",
]
PROMPT_ENTITY_STOPWORDS = {
    "which", "what", "who", "is", "are", "was", "were", "the", "a", "an",
    "better", "best", "game", "movie", "show", "book", "song", "than",
    "between", "compare", "comparing", "tell", "me", "about", "explain",
    "should", "i", "choose", "and",
}
def estimate_energy_kwh(latency_ms, watts):
    return ((latency_ms / 1000) * watts) / 3600 / 1000
def prompt_complexity_score(prompt: str):
    prompt_lower = prompt.lower()
    word_count = len(prompt.split())
    score = 0
    if word_count > 12:
        score += 1
    if word_count > 20:
        score += 2
    if word_count > 35:
        score += 2
    for keyword in COMPLEX_KEYWORDS:
        if keyword in prompt_lower:
            if keyword in ["essay", "detailed", "analysis", "comprehensive", "report", "10-page", "long-form", "news", "today", "2024", "2025", "2026", "current", "latest"]:
                score += 4
            else:
                score += 2
    question_count = prompt.count("?")
    if question_count >= 2:
        score += 2
    clause_markers = [",", ";", " because ", " while ", " versus ", " vs ", " pros and cons "]
    score += sum(1 for marker in clause_markers if marker in prompt_lower)
    return score
def should_use_groq(prompt: str, route_used: str, local_response: str | None = None):
    prompt_lower = prompt.lower()
    complexity = prompt_complexity_score(prompt)
    if "[groq]" in prompt_lower:
        print(f"DEBUG: Groq forced by tag. Complexity: {complexity}")
        return True
    if route_used in ["deterministic", "template_engine", "rejected"]:
        return False
    if complexity >= 4:
        print(f"DEBUG: Groq triggered by complexity ({complexity}). Route was {route_used}")
        return True
    if local_response and is_weak_response(prompt, local_response):
        print(f"DEBUG: Groq triggered by weak response.")
        return True
    return False
def normalize_entity_terms(text: str):
    return [
        token for token in re.findall(r"[a-zA-Z0-9]+", text.lower())
        if len(token) >= 4 and token not in PROMPT_ENTITY_STOPWORDS
    ]
def clean_entity_fragment(text: str):
    return re.sub(
        r"^(which|what|who)\s+(is|are)\s+|^(compare|comparing)\s+|^(tell me about)\s+|^(explain)\s+|^(define)\s+|^(opinions? on)\s+|^(thoughts on)\s+|^(should i buy)\s+|^(should i play)\s+|^(should i watch)\s+",
        "",
        text.strip(" ?.,"),
        flags=re.IGNORECASE,
    )
def extract_comparison_entities(prompt_text: str):
    prompt_clean = " ".join(prompt_text.strip().split())
    prompt_lower = prompt_clean.lower()
    split_match = re.search(r"\b(or|vs|versus)\b", prompt_lower)
    if not split_match:
        return []
    idx_start = split_match.start()
    idx_end = split_match.end()
    left_raw = prompt_clean[:idx_start].strip(" ?.,")
    right_raw = prompt_clean[idx_end:].strip(" ?.,")
    left_raw = re.sub(
        r"^(which|what)\s+(is|are)\s+|^(compare|comparing)\s+|^(which|what)\s+.+?\bbetween\b\s+",
        "",
        left_raw,
        flags=re.IGNORECASE,
    )
    left_terms = normalize_entity_terms(left_raw)
    right_terms = normalize_entity_terms(right_raw)
    if not left_terms or not right_terms:
        return []
    return [left_terms[-3:], right_terms[:3]]
def extract_prompt_entity_groups(prompt_text: str):
    groups = []
    comparison_groups = extract_comparison_entities(prompt_text)
    if comparison_groups:
        groups.extend(comparison_groups)
    prompt_clean = " ".join(prompt_text.strip().split())
    for quoted in re.findall(r'"([^"]+)"|\'([^\']+)\'', prompt_clean):
        phrase = next((part for part in quoted if part), "")
        terms = normalize_entity_terms(phrase)
        if terms:
            groups.append(terms[:4])
    single_subject_patterns = [
        r"^(?:who|what)\s+(?:is|are)\s+(.+)$",
        r"^tell me about\s+(.+)$",
        r"^explain\s+(.+)$",
        r"^define\s+(.+)$",
        r"^opinions?\s+on\s+(.+)$",
        r"^thoughts?\s+on\s+(.+)$",
        r"^should i (?:buy|play|watch)\s+(.+)$",
    ]
    for pattern in single_subject_patterns:
        match = re.search(pattern, prompt_clean, flags=re.IGNORECASE)
        if match:
            subject = clean_entity_fragment(match.group(1))
            terms = normalize_entity_terms(subject)
            if terms:
                groups.append(terms[:4])
            break
    deduped = []
    seen = set()
    for group in groups:
        key = tuple(group)
        if key not in seen:
            seen.add(key)
            deduped.append(group)
    return deduped
def is_high_signal_entity_group(entity_terms):
    if not entity_terms:
        return False
    high_signal_terms = [
        term for term in entity_terms
        if any(ch.isdigit() for ch in term) or len(term) >= 7
    ]
    if high_signal_terms:
        return True
    return len([term for term in entity_terms if len(term) >= 5]) >= 2
def misses_prompt_entities(prompt_text: str, response_text: str):
    response_terms = set(normalize_entity_terms(response_text))
    for entity_terms in extract_prompt_entity_groups(prompt_text):
        if not is_high_signal_entity_group(entity_terms):
            continue
        required_terms = [
            term for term in entity_terms
            if any(ch.isdigit() for ch in term) or len(term) >= 5
        ]
        if required_terms and any(term not in response_terms for term in required_terms):
            return True
    return False
def is_weak_response(prompt_text: str, text: str):
    text_lower = text.lower().strip()
    if len(prompt_text.split()) <= 5:
        return False
    if len(text) < 60:
        return True
    if misses_prompt_entities(prompt_text, text):
        return True
    weak_phrases = [
        "i don't know",
        "i am not aware",
        "i'm not sure",
        "i cannot say",
        "i don't have that information",
        "i don't have access to that",
        "i don't have the ability",
        "i don't have the capability",
        "not sure",
        "i'm not sure",
        "i cannot determine",
        "i can't determine",
        "cannot determine",
        "not enough information",
        "unable to provide",
        "cannot provide",
        "open problem",
        "unsolved problem",
        "i can't provide",
        "i cannot provide",
        "brief overview",
        "high-level overview"
    ]
    if any(w in text_lower for w in weak_phrases):
        return True
    if text.endswith("..."):
        return True
    if not text.endswith((".", "!", "?")):
        return True
    return False
def kb_match_is_relevant(prompt: str, candidate_text: str, score: int):
    if not candidate_text or score <= 0:
        return False
    prompt_tokens = set(tokenize(prompt))
    candidate_tokens = set(tokenize(candidate_text))
    overlap = prompt_tokens & candidate_tokens
    rare_overlap = {token for token in overlap if len(token) >= 5}
    system_design_overlap = overlap & SYSTEM_DESIGN_KEYWORDS
    prompt_system_design_terms = prompt_tokens & SYSTEM_DESIGN_KEYWORDS
    if score < 8:
        return False
    if prompt_complexity_score(prompt) >= 4:
        if len(rare_overlap) < 2:
            return False
        if len(prompt_system_design_terms) >= 2 and not system_design_overlap:
            return False
    return True
def explicitly_requests_code(prompt: str):
    prompt_lower = prompt.lower()
    return any(term in prompt_lower for term in EXPLICIT_CODE_REQUEST_TERMS)
def is_simple_prompt(prompt: str):
    prompt_clean = prompt.strip()
    word_count = len(prompt_clean.split())
    prompt_lower = prompt_clean.lower()
    simple_starters = [
        "what is",
        "who is",
        "define",
        "meaning of",
        "explain",
    ]
    return (
        prompt_complexity_score(prompt_clean) <= 1
        and word_count <= 10
        and any(prompt_lower.startswith(starter) for starter in simple_starters)
    )
def web_search_is_configured():
    return bool(GEMINI_API_KEY)


def get_last_user_message(history: list):
    for msg in reversed(history):
        role = msg.role if hasattr(msg, "role") else msg.get("role")
        content = msg.content if hasattr(msg, "content") else msg.get("content", "")
        if role == "user" and content:
            return " ".join(content.strip().split())
    return ""


def get_last_substantive_user_message(history: list):
    for msg in reversed(history):
        role = msg.role if hasattr(msg, "role") else msg.get("role")
        content = msg.content if hasattr(msg, "content") else msg.get("content", "")
        if role != "user" or not content:
            continue
        compact = " ".join(content.strip().split())
        if not is_short_follow_up(compact):
            return compact
    return get_last_user_message(history)


def get_last_assistant_message(history: list):
    for msg in reversed(history):
        role = msg.role if hasattr(msg, "role") else msg.get("role")
        content = msg.content if hasattr(msg, "content") else msg.get("content", "")
        if role == "assistant" and content:
            return " ".join(content.strip().split())
    return ""


def is_short_follow_up(prompt: str):
    prompt_clean = " ".join(prompt.strip().split()).lower()
    if not prompt_clean:
        return False
    word_count = len(prompt_clean.split())
    follow_up_starters = (
        "and ",
        "what about",
        "what are",
        "which ones",
        "those",
        "that",
        "them",
        "the dates",
        "dates",
        "when",
        "where",
        "who",
        "price",
    )
    return word_count <= 6 or prompt_clean.startswith(follow_up_starters)


def normalize_follow_up_prompt(prompt: str):
    prompt_clean = " ".join(prompt.strip().split())
    prompt_lower = prompt_clean.lower()
    replacements = {
        "thee dates?": "the dates?",
        "thee dates": "the dates",
        "so list them too": "list them too",
        "list them too": "list all of them",
        "the dates?": "list the dates of the games",
        "the dates": "list the dates of the games",
        "dates?": "list the dates of the games",
        "dates": "list the dates of the games",
    }
    return replacements.get(prompt_lower, prompt_clean)


def build_follow_up_search_query(prompt: str, history: list):
    previous_user = get_last_substantive_user_message(history)
    if not previous_user or not is_short_follow_up(prompt):
        return prompt
    prompt_clean = normalize_follow_up_prompt(prompt)
    return f"{previous_user} {prompt_clean}"


def extract_hostname(url: str):
    try:
        hostname = urlparse(url).hostname or ""
    except Exception:
        return ""
    return hostname.lower().removeprefix("www.")


def hostname_matches(hostname: str, pattern: str):
    normalized = pattern.lower().removeprefix("www.")
    return hostname == normalized or hostname.endswith(f".{normalized}") or hostname.endswith(normalized)


def classify_query_topic(query: str):
    text = query.lower()
    if any(term in text for term in ("premier league", "fixture", "fixtures", "match", "score", "ipl", "epl", "football", "soccer", "nba", "nfl")):
        return "sports"
    if any(term in text for term in ("price", "stock", "bitcoin", "ethereum", "solana", "gold", "usd", "inr", "crypto", "exchange rate")):
        return "finance"
    if any(term in text for term in ("school", "college", "university", "admission", "board exam", "curriculum")):
        return "education"
    return "general"


def score_source_for_topic(source: dict, topic: str):
    hostname = extract_hostname(source.get("url", ""))
    title = (source.get("title", "") or "").lower()
    if not hostname:
        return -1000
    if any(hostname_matches(hostname, blocked) for blocked in BLOCKED_SOURCE_DOMAINS):
        return -1000

    score = 0
    preferred = TOPIC_PREFERRED_DOMAINS.get(topic, ())
    if any(hostname_matches(hostname, allowed) for allowed in preferred):
        score += 100
    if any(hostname_matches(hostname, trusted) for trusted in GENERIC_TRUSTED_DOMAINS):
        score += 40
    if hostname.endswith(".gov") or hostname.endswith(".gov.in") or hostname.endswith(".edu") or hostname.endswith(".ac.in"):
        score += 35
    if topic == "sports" and any(term in title for term in ("fixture", "fixtures", "premier league", "match")):
        score += 10
    if topic == "finance" and any(term in title for term in ("price", "market", "exchange", "rate", "gold", "bitcoin", "ethereum", "solana")):
        score += 10
    if topic == "education" and any(term in title for term in ("school", "admission", "curriculum", "campus")):
        score += 10
    return score


def filter_and_rank_sources(query: str, sources: list[dict]):
    topic = classify_query_topic(query)
    scored = []
    for source in sources:
        score = score_source_for_topic(source, topic)
        if score > -1000:
            scored.append((score, source))
    scored.sort(key=lambda item: item[0], reverse=True)
    filtered = [source for score, source in scored if score > 0][:5]
    if filtered:
        return filtered
    return [source for score, source in scored][:3]


def run_google_grounded_search(query: str):
    if not web_search_is_configured():
        return None
    try:
        response = requests.post(
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent",
            headers={
                "x-goog-api-key": GEMINI_API_KEY,
                "Content-Type": "application/json",
            },
            json={
                "contents": [
                    {
                        "parts": [
                            {
                                "text": (
                                    "Answer using Google Search grounding. "
                                    "Be concise, factual, and cite only information supported by search results.\n\n"
                                    f"{query}"
                                )
                            }
                        ]
                    }
                ],
                "tools": [
                    {
                        "google_search": {}
                    }
                ]
            },
            timeout=25,
        )
        response.raise_for_status()
        return response.json()
    except Exception as exc:
        print(f"DEBUG: web search failed: {exc}")
        return None


def extract_gemini_grounded_response(payload: dict):
    candidates = payload.get("candidates") or []
    if not candidates:
        return "", []
    candidate = candidates[0] or {}
    content = candidate.get("content") or {}
    parts = content.get("parts") or []
    text = "".join(part.get("text", "") for part in parts if isinstance(part, dict)).strip()
    grounding = candidate.get("groundingMetadata") or {}
    chunks = grounding.get("groundingChunks") or []
    sources = []
    seen = set()
    for chunk in chunks:
        web = chunk.get("web") or {}
        url = web.get("uri", "").strip()
        title = web.get("title", "").strip()
        if not url or url in seen:
            continue
        seen.add(url)
        sources.append({"title": title or url, "url": url})
    return text, sources


def build_web_context_prompt(prompt: str, grounded_text: str, sources: list[dict]):
    source_lines = []
    for idx, source in enumerate(sources[:5], start=1):
        title = source.get("title", "").strip() or f"Source {idx}"
        url = source.get("url", "").strip()
        source_lines.append(f"{idx}. {title}\n{url}")
    sources_block = "\n\n".join(source_lines) if source_lines else "No sources returned."
    return (
        "Use the web context below to answer the user's question. "
        "Answer only from the provided web context and cited sources. "
        "If the context is insufficient or unclear, say so briefly. "
        "Do not claim you searched the web yourself.\n\n"
        "Do not include a 'Sources' section, numbered source list, or raw URLs in the answer body.\n\n"
        f"Web context:\n{grounded_text}\n\n"
        f"Sources:\n{sources_block}\n\n"
        f"Question: {prompt}"
    )


def strip_trailing_sources_block(text: str):
    cleaned = (text or "").strip()
    patterns = [
        r"\n{2,}Sources:\s*\n(?:.+\n?)*$",
        r"\n{2,}\d+\.\s+[^\n]+\n(?:\d+\.\s+[^\n]+\n?)*$",
        r"\n{2,}(?:[-*]\s+\[[^\]]+\]\([^)]+\)\n?)+$",
    ]
    for pattern in patterns:
        updated = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)
        if updated != cleaned:
            cleaned = updated.strip()
    return cleaned


def format_web_answer_with_local(prompt: str, grounded_text: str):
    formatting_prompt = (
        "Rewrite the web-grounded answer below for a user-facing chat response. "
        "Do not add, remove, or change any factual content. "
        "Do not introduce new claims, dates, names, or numbers. "
        "Do not mention sources, search, web context, APIs, or implementation details. "
        "Keep the answer clear and concise. "
        "If the answer is already concise, preserve it closely.\n\n"
        f"User question: {prompt}\n\n"
        f"Answer to rewrite:\n{grounded_text}"
    )
    formatted = strip_trailing_sources_block(run_local_model(formatting_prompt, [], prompt))
    if not formatted:
        return grounded_text
    if is_weak_response(prompt, formatted):
        return grounded_text
    return formatted


def run_web_search_route(prompt: str, history: list = []):
    if not web_search_is_configured():
        return {"route": "rejected", "response": "Web search is on, but GEMINI_API_KEY is missing in .env.", "sources": []}
    search_query = build_follow_up_search_query(prompt, history)
    payload = run_google_grounded_search(search_query)
    if not payload:
        return {"route": "web", "response": "I could not refresh web results for that follow-up. Please restate the topic a bit more specifically.", "sources": []}
    grounded_text, sources = extract_gemini_grounded_response(payload)
    if not grounded_text:
        last_assistant = get_last_assistant_message(history)
        if last_assistant and is_short_follow_up(prompt):
            fallback_prompt = (
                "Use the previous assistant answer below to answer the user's follow-up if the answer is directly supported by that context. "
                "If the context is not enough, say you need a more specific follow-up.\n\n"
                f"Previous assistant answer:\n{last_assistant}\n\n"
                f"Follow-up question: {prompt}"
            )
            fallback_response = strip_trailing_sources_block(run_local_model(fallback_prompt, history, prompt))
            return {"route": "web", "response": fallback_response, "sources": []}
        return {"route": "web", "response": "I could not get grounded web results for that follow-up. Please restate it more specifically.", "sources": filter_and_rank_sources(prompt, sources)}
    trusted_sources = filter_and_rank_sources(search_query, sources)
    visible_grounded_text = strip_trailing_sources_block(grounded_text)
    formatted_response = format_web_answer_with_local(prompt, visible_grounded_text)
    return {"route": "web", "response": formatted_response, "sources": trusted_sources}


def select_max_tokens(prompt: str):
    if explicitly_requests_code(prompt):
        return 420
    if is_simple_prompt(prompt):
        return 120
    if prompt_complexity_score(prompt) >= 4:
        return 400
    return 280
def response_looks_truncated(prompt: str, text: str):
    text = text.strip()
    if not text:
        return True
    if "question:" in text.lower():
        return False
    if explicitly_requests_code(prompt):
        lines = [line.rstrip() for line in text.splitlines() if line.strip()]
        if not lines:
            return True
        last_line = lines[-1].strip()
        if last_line.endswith((":", ",", "(", "[", "{")):
            return True
        if last_line.startswith(("def ", "class ", "if ", "for ", "while ", "elif ", "else", "try", "except", "with ")) and not last_line.endswith(")"):
            return True
        return False
    if len(text) < 80 and not text.endswith((".", "!", "?")):
        return True
    if text.endswith(("...", ":", ",", ";", "-", " and", " or", " but", " because", " which", " that", " provides", " includes")):
        return True
    return not text.endswith((".", "!", "?"))
def _clean_memory_value(value: str):
    value = value.strip(" .,!?:;\"\x27")
    value = re.sub(r"\s+", " ", value)
    return value[:120]
def extract_user_memories(history: list, limit: int = 10):
    patterns = [
        (r"\bmy name is ([a-zA-Z][a-zA-Z\s-]{0,40})", "User name"),
        (r"\bcall me ([a-zA-Z][a-zA-Z\s-]{0,40})", "User prefers to be called"),
        (r"\bi live in ([a-zA-Z0-9,\s-]{1,60})", "User lives in"),
        (r"\bi am from ([a-zA-Z0-9,\s-]{1,60})", "User is from"),
        (r"\bi\x27m from ([a-zA-Z0-9,\s-]{1,60})", "User is from"),
        (r"\bi work as ([a-zA-Z0-9,\s-]{1,60})", "User works as"),
        (r"\bi am a[n]? ([a-zA-Z0-9,\s-]{1,60})", "User is a"),
        (r"\bi\x27m a[n]? ([a-zA-Z0-9,\s-]{1,60})", "User is a"),
        (r"\bi like ([a-zA-Z0-9,\s-]{1,80})", "User likes"),
        (r"\bi love ([a-zA-Z0-9,\s-]{1,80})", "User loves"),
        (r"\bi prefer ([a-zA-Z0-9,\s-]{1,80})", "User prefers"),
        (r"\bmy favorite ([a-zA-Z0-9\s-]{1,40}) is ([a-zA-Z0-9,\s-]{1,60})", "User favorite"),
        (r"\bi am building ([a-zA-Z0-9,\s-]{1,80})", "User is building"),
        (r"\bi\x27m building ([a-zA-Z0-9,\s-]{1,80})", "User is building"),
        (r"\bi am working on ([a-zA-Z0-9,\s-]{1,80})", "User is working on"),
        (r"\bi\x27m working on ([a-zA-Z0-9,\s-]{1,80})", "User is working on"),
        (r"\bmy project is ([a-zA-Z0-9,\s-]{1,80})", "User project"),
        (r"\bi use ([a-zA-Z0-9,\s._:-]{1,60})", "User uses"),
    ]
    memories = []
    seen = set()
    for msg in history:
        role = msg.role if hasattr(msg, "role") else msg.get("role")
        content = msg.content if hasattr(msg, "content") else msg.get("content", "")
        if role != "user" or not content:
            continue
        text = " ".join(content.strip().split())
        for pattern, label in patterns:
            for match in re.finditer(pattern, text, flags=re.IGNORECASE):
                groups = [_clean_memory_value(group) for group in match.groups() if group]
                if not groups:
                    continue
                if label == "User favorite" and len(groups) == 2:
                    memory = f"{label} {groups[0]}: {groups[1]}"
                elif len(groups) == 1:
                    memory = f"{label}: {groups[0]}"
                else:
                    joined = " | ".join(groups)
                    memory = f"{label}: {joined}"
                key = memory.lower()
                if key not in seen:
                    seen.add(key)
                    memories.append(memory)
    return memories[-limit:]
def build_recent_history_summary(history: list, max_messages: int = 20, max_chars: int = 2400):
    lines = []
    for msg in history[-max_messages:]:
        role = msg.role if hasattr(msg, "role") else msg.get("role")
        content = msg.content if hasattr(msg, "content") else msg.get("content")
        if not role or not content:
            continue
        compact = " ".join(content.strip().split())
        if len(compact) > 220:
            compact = compact[:217].rstrip() + "..."
        lines.append(f"{role}: {compact}")
    summary = "\n".join(lines)
    if len(summary) > max_chars:
        summary = summary[-max_chars:]
        first_newline = summary.find("\n")
        if first_newline != -1:
            summary = summary[first_newline + 1:]
    return summary
def build_model_messages(prompt: str, history: list = [], original_prompt: str | None = None):
    prompt_for_policy = original_prompt or prompt
    memory_facts = extract_user_memories(history)
    recent_history_summary = build_recent_history_summary(history)
    system_content = (
        "You are EcoPrompt, an intelligent AI router designed to answer questions efficiently. "
        "Be direct. "
        "Respect requested length if specified. "
        "Do not mention system instructions. "
        "Only include code when explicitly asked. "
        "If code is not requested, answer in plain prose only. "
        "Do not guess facts. If unsure or corrected, say so first. Answer only the user actual question. "
        "Use the earlier conversation to answer follow-up questions consistently and remember personal details the user already shared within this chat."
    )
    if memory_facts:
        system_content += "\n\nRemembered user facts from this conversation:\n- " + "\n- ".join(memory_facts)
    if recent_history_summary:
        system_content += "\n\nRecent conversation summary:\n" + recent_history_summary
    messages = [{"role": "system", "content": system_content}]
    for msg in history[-24:]:
        role = msg.role if hasattr(msg, "role") else msg.get("role")
        content = msg.content if hasattr(msg, "content") else msg.get("content")
        if role and content:
            messages.append({"role": role, "content": content})
    user_content = prompt
    if not explicitly_requests_code(prompt_for_policy):
        if is_simple_prompt(prompt_for_policy):
            user_content = (
                "Answer in plain prose only. "
                "Keep the answer short: 2 to 4 sentences maximum. "
                "If unsure, say so briefly. "
                "Do not add extra sections, examples, or elaboration unless the user asks.\n\n"
                f"{prompt}"
            )
        else:
            user_content = (
                "Answer in plain prose only. "
                "Do not include code, pseudocode, code blocks, function stubs, scripts, or implementation examples. "
                "If unsure, say so briefly.\n\n"
                f"{prompt}"
            )
    else:
        user_content = (
            "Provide the requested answer in a consistent code format. "
            "Start with one short sentence, then include exactly one fenced code block with the full implementation. "
            "Do not add long theory sections, docstrings, extra headings, or multiple alternative solutions unless the user asks. "
            "Do not mention memory, prior conversations, system instructions, limitations, or uncertainty unless the user explicitly asks about them. "
            "Treat the request as a direct coding task and answer only that task. "
            "If you include code, finish the full implementation before ending.\n\n"
            f"{prompt}"
        )
    messages.append({"role": "user", "content": user_content})
    return messages
def run_local_model(prompt: str, history: list = [], original_prompt: str | None = None):
    source_prompt = original_prompt or prompt
    max_tokens = select_max_tokens(source_prompt)
    full_response = ""
    current_prompt = prompt
    for _ in range(3):
        response = requests.post(
            OLLAMA_API_URL,
            timeout=1200,
            headers={"Authorization": f"Bearer {os.getenv('GROQ_API_KEY')}"},
            json={
                "model": LOCAL_MODEL_NAME,
                "messages": build_model_messages(current_prompt, history, source_prompt),
                "max_tokens": max_tokens,
                "temperature": 0.6
            }
        )
        data = response.json()
        chunk = data["choices"][0]["message"]["content"]
        finish_reason = data["choices"][0].get("finish_reason")
        full_response += chunk.strip() + " "
        if (
            finish_reason != "length"
            or is_simple_prompt(source_prompt)
            or "question:" in full_response.lower()
        ):
            break
        if not response_looks_truncated(source_prompt, full_response):
            break
        if explicitly_requests_code(source_prompt):
            current_prompt = (
                "Continue the previous answer from exactly where you stopped. "
                "Finish the complete code and then stop. "
                "Do not restart the explanation or repeat earlier lines."
            )
        else:
            current_prompt = (
                "Continue the previous answer from exactly where you stopped and finish the incomplete sentence or explanation. "
                "Do not restart from the beginning or repeat earlier content."
            )
    full_response = full_response.strip()
    if explicitly_requests_code(source_prompt):
        return normalize_code_response(source_prompt, full_response)
    return full_response
def run_groq(prompt: str, history: list = []):
    completion = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=build_model_messages(prompt, history),
    )
    return completion.choices[0].message.content
def stream_groq(prompt: str, history: list = []):
    completion = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=build_model_messages(prompt, history),
        stream=True
    )
    for chunk in completion:
        token = chunk.choices[0].delta.content
        if token:
            yield token
def stream_groq_with_metrics(prompt, history, route_used, start_time):
    try:
        for token in stream_groq(prompt, history):
            yield token
    finally:
        finalize_stream_metrics(route_used, start_time, 250)

def format_template_code_response(prompt: str, code: str):
    language = "python"
    title = prompt.strip().rstrip("?.!") or "Code Example"
    return f"Here is a concise {language} example for {title}:\n\n```{language}\n{code.strip()}\n```"

def normalize_code_response(prompt: str, response: str):
    text = (response or "").strip()
    if not text or "```" in text:
        return text

    title = prompt.strip().rstrip("?.!") or "Code Example"
    lines = [line.rstrip() for line in text.splitlines()]
    code_start = None
    code_markers = (
        "def ", "class ", "import ", "from ", "if ", "for ", "while ", "try:", "with ",
        "return ", "const ", "let ", "var ", "function ", "#include", "public ", "private "
    )

    for idx, line in enumerate(lines):
        stripped = line.lstrip()
        if not stripped:
            continue
        if stripped.startswith(code_markers):
            code_start = idx
            break

    if code_start is None and text.startswith(code_markers):
        code_start = 0

    if code_start is None:
        return f"Here is a concise python example for {title}:\n\n```python\n{text}\n```"

    intro_lines = [line.strip() for line in lines[:code_start] if line.strip()]
    code_lines = lines[code_start:] if code_start < len(lines) else lines
    intro = " ".join(intro_lines) if intro_lines else f"Here is a concise python example for {title}:"
    code = "\n".join(code_lines).strip()
    return f"{intro}\n\n```python\n{code}\n```"

def template_engine(prompt: str):
    prompt_lower = prompt.lower()
    if not explicitly_requests_code(prompt):
        return None
    for template in CODE_TEMPLATES:
        for keyword in template["keywords"]:
            if keyword in prompt_lower:
                return format_template_code_response(prompt, template["content"])
    return None

def stream_local_response(prompt: str, history: list, original_prompt: str, route_used: str, start_time: float):
    try:
        current_prompt = prompt
        full_response = ""
        for _ in range(3):
            response = None
            finish_reason = None
            try:
                response = requests.post(
                    OLLAMA_API_URL,
                    stream=True,
                    headers={"Authorization": f"Bearer {os.getenv('GROQ_API_KEY')}"},
                    json={
                        "model": LOCAL_MODEL_NAME,
                        "messages": build_model_messages(current_prompt, history, original_prompt),
                        "temperature": 0.6,
                        "max_tokens": select_max_tokens(original_prompt),
                        "stream": True
                    }
                )
                buffer = ""
                for chunk in response.iter_content(chunk_size=1024):
                    if not chunk:
                        continue
                    buffer += chunk.decode("utf-8")
                    lines = buffer.split("\n")
                    buffer = lines.pop()
                    for line in lines:
                        if not line.startswith("data: "):
                            continue
                        data = line[6:].strip()
                        if data == "[DONE]":
                            break
                        try:
                            json_data = json.loads(data)
                            choice = json_data["choices"][0]
                            token = choice["delta"].get("content")
                            finish_reason = choice.get("finish_reason") or finish_reason
                            if token:
                                full_response += token
                                yield token
                        except Exception:
                            continue
            finally:
                if response is not None:
                    response.close()
            if (
                finish_reason != "length"
                or is_simple_prompt(original_prompt)
                or "question:" in full_response.lower()
                or not response_looks_truncated(original_prompt, full_response)
            ):
                break
            if explicitly_requests_code(original_prompt):
                current_prompt = (
                    "Continue the previous answer from exactly where you stopped. "
                    "Finish the complete code and then stop. "
                    "Do not restart the explanation or repeat earlier lines."
                )
            else:
                current_prompt = (
                    "Continue the previous answer from exactly where you stopped and finish the incomplete sentence or explanation. "
                    "Do not restart from the beginning or repeat earlier content."
                )
    finally:
        finalize_stream_metrics(route_used, start_time, 35)

@app.post("/generate")
def generate(request: PromptRequest, http_request: Request):
    _enforce_limit(http_request)
    start_time = time.time()
    prompt = request.prompt.strip()
    if len(prompt) < 2:
        update_route_metrics("rejected", 0, 0)
        return {
            "level_used": "rejected",
            "latency_ms": 0,
            "response": "Please enter a meaningful question."
        }
    if not any(c.isalpha() for c in prompt) and not any(c.isdigit() for c in prompt):
        update_route_metrics("rejected", 0, 0)
        return {
            "level_used": "rejected",
            "latency_ms": 0,
            "response": "Input does not appear to be valid."
        }

    det_result = deterministic_engine(prompt)
    if det_result:
        update_route_metrics("deterministic", 0, 0)
        return {
            "level_used": "deterministic",
            "latency_ms": 0,
            "response": det_result
        }

    if request.web_search:
        web_result = run_web_search_route(prompt, request.history)
        route_used = web_result["route"]
        latency_ms = round((time.time() - start_time) * 1000, 2)
        watts = 250 if route_used == "groq" else 35
        energy_kwh = estimate_energy_kwh(latency_ms, watts)
        update_route_metrics(route_used, latency_ms, energy_kwh)
        record_history(route_used, latency_ms, energy_kwh)
        return {
            "level_used": route_used,
            "latency_ms": latency_ms,
            "response": web_result["response"],
            "sources": web_result["sources"],
        }

    if explicitly_requests_code(prompt):
        template_result = template_engine(prompt)
        if template_result:
            latency_ms = round((time.time() - start_time) * 1000, 2)
            energy_kwh = estimate_energy_kwh(latency_ms, 10)
            update_route_metrics("template_engine", latency_ms, energy_kwh)
            record_history("template_engine", latency_ms, energy_kwh)
            return {
                "level_used": "template_engine",
                "latency_ms": latency_ms,
                "response": template_result
            }

        response = run_local_model(prompt, request.history, prompt)
        latency_ms = round((time.time() - start_time) * 1000, 2)
        energy_kwh = estimate_energy_kwh(latency_ms, 35)
        update_route_metrics("local", latency_ms, energy_kwh)
        record_history("local", latency_ms, energy_kwh)
        return {
            "level_used": "local",
            "latency_ms": latency_ms,
            "response": response
        }

    lookups = [
        ("geography", geography_lookup),
        ("math", math_lookup),
        ("science", science_lookup),
        ("history", history_lookup),
        ("programming", programming_lookup),
        ("high_level", high_level_lookup),
    ]
    kb_results = []
    for name, lookup in lookups:
        result = lookup(prompt)
        if result:
            response, score = result
            kb_results.append((name, response, score))

    if kb_results:
        best_domain, best_response, best_score = max(
            kb_results,
            key=lambda x: x[2]
        )
        if kb_match_is_relevant(prompt, best_response, best_score):
            kb_prompt = f"""
Context:
{best_response}
Question: {prompt}
"""
            model_response = run_local_model(kb_prompt, request.history, prompt)
            latency_ms = round((time.time() - start_time) * 1000, 2)
            energy_kwh = estimate_energy_kwh(latency_ms, 35)
            update_route_metrics("kb_reasoned_local", latency_ms, energy_kwh)
            record_history("kb_reasoned_local", latency_ms, energy_kwh)
            return {
                "level_used": "kb_reasoned_local",
                "latency_ms": latency_ms,
                "response": model_response
            }

    rag_docs = retrieve_top_k(prompt, k=1, min_score=7)
    if rag_docs:
        doc = rag_docs[0]
        title = doc.get("title", "")
        content = doc.get("content") or doc.get("description") or ""
        formula = doc.get("formula")
        rag_context = f"{title}\n{content}"
        if formula:
            rag_context += f"\nFormula: {formula}"
        if kb_match_is_relevant(prompt, rag_context, 8):
            rag_prompt = f"""
Context:
{rag_context}
Question: {prompt}
"""
            model_response = run_local_model(rag_prompt, request.history, prompt)
            latency_ms = round((time.time() - start_time) * 1000, 2)
            energy_kwh = estimate_energy_kwh(latency_ms, 35)
            update_route_metrics("rag_local", latency_ms, energy_kwh)
            record_history("rag_local", latency_ms, energy_kwh)
            return {
                "level_used": "rag_local",
                "latency_ms": latency_ms,
                "response": model_response
            }

    local_response = run_local_model(prompt, request.history, prompt)
    if should_use_groq(prompt, "local", local_response):
        response = run_groq(prompt, request.history)
        level_used = "groq"
        watts = 250
    else:
        response = local_response
        level_used = "local"
        watts = 35

    latency_ms = round((time.time() - start_time) * 1000, 2)
    energy_kwh = estimate_energy_kwh(latency_ms, watts)
    update_route_metrics(level_used, latency_ms, energy_kwh)
    record_history(level_used, latency_ms, energy_kwh)
    return {
        "level_used": level_used,
        "latency_ms": latency_ms,
        "response": response
    }
@app.get("/metrics")
def get_metrics():
    avg_latency = 0
    if metrics["total_prompts"] > 0:
        avg_latency = metrics["total_latency"] / metrics["total_prompts"]
    local_route_names = [
        "deterministic",
        "kb_reasoned_local",
        "rag_local",
        "template_engine",
        "web",
        "local",
    ]
    valid_prompts = metrics["total_prompts"] - metrics["route_counts"].get("rejected", 0)
    local_handled = sum(metrics["route_counts"][route] for route in local_route_names)
    cloud_avoidance_rate = (
        round((local_handled / valid_prompts) * 100, 2)
        if valid_prompts > 0 else 0
    )
    route_averages = {}
    route_energy = {}
    route_distribution = {
        "deterministic": metrics["route_counts"].get("deterministic", 0),
        "knowledge_kb": (
            metrics["route_counts"].get("kb_reasoned_local", 0) +
            metrics["route_counts"].get("rag_local", 0) +
            metrics["route_counts"].get("template_engine", 0)
        ),
        "local": (
            metrics["route_counts"].get("local", 0) +
            metrics["route_counts"].get("web", 0)
        ),
        "groq": metrics["route_counts"].get("groq", 0)
    }
    def get_avg(keys, metric_type):
        total = sum(metrics["route_totals"][k][metric_type] for k in keys if k in metrics["route_totals"])
        count = sum(metrics["route_counts"][k] for k in keys if k in metrics["route_counts"])
        return round(total / count, 4) if count > 0 else 0
    route_averages = {
        "deterministic": get_avg(["deterministic"], "latency_ms"),
        "knowledge_kb": get_avg(["kb_reasoned_local", "rag_local", "template_engine"], "latency_ms"),
        "local": get_avg(["local", "web"], "latency_ms"),
        "groq": get_avg(["groq"], "latency_ms")
    }
    route_energy = {
        "deterministic": get_avg(["deterministic"], "energy_kwh"),
        "knowledge_kb": get_avg(["kb_reasoned_local", "rag_local", "template_engine"], "energy_kwh"),
        "local": get_avg(["local", "web"], "energy_kwh"),
        "groq": get_avg(["groq"], "energy_kwh")
    }
    actual_api_cost_usd = sum(t["estimated_cost_usd"] for t in metrics["route_totals"].values())
    INR_CONVERSION = 83
    actual_api_cost_inr = actual_api_cost_usd * INR_CONVERSION
    electricity_cost_inr = metrics["total_energy_kwh"] * ELECTRICITY_COST_INR_PER_KWH
    total_actual_spend_inr = round(actual_api_cost_inr + electricity_cost_inr, 2)
    hypothetical_gpt4o_cost_usd = valid_prompts * COST_GPT4O_BASELINE
    gpt4o_baseline_inr = round(hypothetical_gpt4o_cost_usd * INR_CONVERSION, 2)
    co2_saved_kg = round(electricity_cost_inr * 0.05, 4) # Simple heuristic for offset
    try:
        estimated_cost_saved_inr = round(max(gpt4o_baseline_inr - total_actual_spend_inr, 0), 2)
        return {
            "total_prompts": valid_prompts,
            "avg_latency_ms": round(metrics["total_latency"] / valid_prompts, 2) if valid_prompts > 0 else 0,
            "total_energy_kwh": round(metrics["total_energy_kwh"], 6),
            "route_distribution": route_distribution,
            "route_avg_latency_ms": route_averages,
            "route_energy_kwh": route_energy,
            "cloud_avoidance_rate": cloud_avoidance_rate,
            "fallback_rate_groq": round(
                (metrics["route_counts"]["groq"] / valid_prompts) * 100, 2
            ) if valid_prompts > 0 else 0,
            "estimated_cost_usd": total_actual_spend_inr, 
            "gpt4o_baseline_cost_inr": gpt4o_baseline_inr,
            "estimated_cost_saved_usd": estimated_cost_saved_inr, 
            "co2_offset_kg": co2_saved_kg,
            "route_distribution_chart": route_distribution,
            "history": [h for h in metrics["history"] if "route" in h and h["route"] != "rejected"]
        }
    except Exception as e:
        print(f"Metrics Error: {e}")
        return {"error": "Could not calculate full metrics"}
from fastapi.responses import StreamingResponse
@app.post("/generate-stream")
def generate_stream(request: PromptRequest, http_request: Request):
    _enforce_limit(http_request)
    start_time = time.time()
    prompt = request.prompt.strip()
    original_prompt = prompt
    route_used = "local"
    if len(prompt) < 2 or (not any(c.isalpha() for c in prompt) and not any(c.isdigit() for c in prompt)):
        update_route_metrics("rejected", 0, 0)
        def _reject_stream():
            yield "Please enter a meaningful question."
        return StreamingResponse(_reject_stream(), media_type="text/plain", headers={"X-Route": "rejected"})
    det_result = deterministic_engine(prompt)
    if det_result:
        route_used = "deterministic"
        def _stream_deterministic():
            try:
                yield det_result
            finally:
                latency_ms = round((time.time() - start_time) * 1000, 2)
                update_route_metrics("deterministic", latency_ms, 0)
                record_history("deterministic", latency_ms, 0)
        return StreamingResponse(
            _stream_deterministic(),
            media_type="text/plain",
            headers={"X-Route": route_used}
        )

    if request.web_search:
        web_result = run_web_search_route(original_prompt, request.history)
        route_used = web_result["route"]
        source_header = json.dumps(web_result["sources"], separators=(",", ":"))

        def _stream_web():
            try:
                yield web_result["response"]
            finally:
                latency_ms = round((time.time() - start_time) * 1000, 2)
                watts = 250 if route_used == "groq" else 35
                energy_kwh = estimate_energy_kwh(latency_ms, watts)
                update_route_metrics(route_used, latency_ms, energy_kwh)
                record_history(route_used, latency_ms, energy_kwh)

        return StreamingResponse(
            _stream_web(),
            media_type="text/plain",
            headers={"X-Route": route_used, "X-Sources": source_header}
        )

    if explicitly_requests_code(prompt):
        template_result = template_engine(prompt)
        if template_result:
            route_used = "template_engine"

            def _stream_template():
                try:
                    yield template_result
                finally:
                    latency_ms = round((time.time() - start_time) * 1000, 2)
                    energy_kwh = estimate_energy_kwh(latency_ms, 10)
                    update_route_metrics("template_engine", latency_ms, energy_kwh)
                    record_history("template_engine", latency_ms, energy_kwh)
            return StreamingResponse(
                _stream_template(),
                media_type="text/plain",
                headers={"X-Route": route_used}
            )

        response = run_local_model(prompt, request.history, original_prompt)

        def _stream_code_response():
            try:
                yield response
            finally:
                finalize_stream_metrics(route_used, start_time, 35)

        return StreamingResponse(
            _stream_code_response(),
            media_type="text/plain",
            headers={"X-Route": route_used}
        )

    lookups = [
        ("geography", geography_lookup),
        ("math", math_lookup),
        ("science", science_lookup),
        ("history", history_lookup),
        ("programming", programming_lookup),
        ("high_level", high_level_lookup),
    ]
    kb_results = []
    for name, lookup in lookups:
        result = lookup(prompt)
        if result:
            response, score = result
            kb_results.append((name, response, score))
    if kb_results:
        best_domain, best_response, best_score = max(
            kb_results,
            key=lambda x: x[2]
        )
        if kb_match_is_relevant(original_prompt, best_response, best_score):
            prompt = f"""
Context:
{best_response}
Question: {prompt}
"""
            route_used = "kb_reasoned_local"
    if route_used == "local":
        rag_docs = retrieve_top_k(prompt, k=1, min_score=8)
        if rag_docs:
            doc = rag_docs[0]
            title = doc.get("title", "")
            content = doc.get("content") or doc.get("description") or ""
            formula = doc.get("formula")
            rag_context = f"{title}\n{content}"
            if formula:
                rag_context += f"\nFormula: {formula}"
            if kb_match_is_relevant(original_prompt, rag_context, 8):
                prompt = f"""
Context:
{rag_context}
            Question: {prompt}
"""
                route_used = "rag_local"
    use_groq = should_use_groq(original_prompt, route_used)
    if use_groq:
        route_used = "groq"
        return StreamingResponse(
            stream_groq_with_metrics(prompt, request.history, route_used, start_time),
            media_type="text/plain",
            headers={"X-Route": route_used}
        )
    else:
        return StreamingResponse(
            stream_local_response(prompt, request.history, original_prompt, route_used, start_time),
            media_type="text/plain",
            headers={"X-Route": route_used}
        )                                       
