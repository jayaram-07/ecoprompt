import json
import os
import re

# Load geography data once at startup
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(BASE_DIR, "geography.json")

with open(DATA_PATH, "r", encoding="utf-8") as f:
    GEO_DATA = json.load(f)

COUNTRIES = GEO_DATA["countries"]
CONTINENTS = GEO_DATA["continents"]
STATES = GEO_DATA["states"]


def geography_lookup(prompt: str):
    prompt_lower = prompt.lower().strip()

    # ----------------------------
    # 1. Capital (Flexible)
    # ----------------------------
    capital_patterns = [
        r"capital of ([a-zA-Z\s]+)",
        r"what is the capital of ([a-zA-Z\s]+)",
        r"capital city of ([a-zA-Z\s]+)"
    ]

    for pattern in capital_patterns:
        match = re.search(pattern, prompt_lower)
        if match:
            country_name = match.group(1).strip().title()
            for country in COUNTRIES:
                if country["name"].lower() == country_name.lower():
                    return f"The capital of {country['name']} is {country['capital']}.", 10

    # ----------------------------
    # 2. Currency (Flexible)
    # ----------------------------
    currency_patterns = [
        r"currency of ([a-zA-Z\s]+)",
        r"what currency does ([a-zA-Z\s]+) use",
        r"what money does ([a-zA-Z\s]+) use",
        r"money of ([a-zA-Z\s]+)"
    ]

    for pattern in currency_patterns:
        match = re.search(pattern, prompt_lower)
        if match:
            country_name = match.group(1).strip().title()
            for country in COUNTRIES:
                if country["name"].lower() == country_name.lower():
                    return f"The currency of {country['name']} is {country['currency']}.", 10

    # ----------------------------
    # 3. Countries in Continent
    # ----------------------------
    continent_match = re.search(r"countries in ([a-zA-Z\s]+)", prompt_lower)
    if continent_match:
        continent_name = continent_match.group(1).strip().title()
        matching = [
            c["name"] for c in COUNTRIES
            if c["continent"].lower() == continent_name.lower()
        ]
        if matching:
            return f"Countries in {continent_name}: {', '.join(matching[:20])}...", 8

    # ----------------------------
    # 4. State Capital
    # ----------------------------
    state_capital_match = re.search(r"capital of ([a-zA-Z\s]+)", prompt_lower)
    if state_capital_match:
        state_name = state_capital_match.group(1).strip().title()
        for country, state_list in STATES.items():
            for state in state_list:
                if state["name"].lower() == state_name.lower():
                    return f"The capital of {state['name']} is {state['capital']}.", 9

    return None, 0