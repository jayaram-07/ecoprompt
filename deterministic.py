import re
import math

# -----------------------------
# Allowed math functions
# -----------------------------

ALLOWED_NAMES = {
    k: getattr(math, k) for k in dir(math) if not k.startswith("_")
}

ALLOWED_NAMES.update({
    "abs": abs,
    "round": round
})

UNIT_ALIASES = {
    "km": "km",
    "kilometer": "km",
    "kilometers": "km",
    "kilometre": "km",
    "kilometres": "km",
    "m": "m",
    "meter": "m",
    "meters": "m",
    "metre": "m",
    "metres": "m",
    "cm": "cm",
    "centimeter": "cm",
    "centimeters": "cm",
    "centimetre": "cm",
    "centimetres": "cm",
    "mile": "mile",
    "miles": "mile",
    "kg": "kg",
    "kilogram": "kg",
    "kilograms": "kg",
    "lb": "lb",
    "lbs": "lb",
    "pound": "lb",
    "pounds": "lb",
    "minute": "minute",
    "minutes": "minute",
    "min": "minute",
    "mins": "minute",
    "second": "second",
    "seconds": "second",
    "sec": "second",
    "secs": "second",
    "hour": "hour",
    "hours": "hour",
    "hr": "hour",
    "hrs": "hour",
    "c": "celsius",
    "celsius": "celsius",
    "f": "fahrenheit",
    "fahrenheit": "fahrenheit",
}

LINEAR_CONVERSIONS = {
    ("km", "mile"): lambda value: value * 0.621371,
    ("mile", "km"): lambda value: value / 0.621371,
    ("kg", "lb"): lambda value: value * 2.20462,
    ("lb", "kg"): lambda value: value / 2.20462,
    ("cm", "m"): lambda value: value / 100,
    ("m", "cm"): lambda value: value * 100,
    ("m", "km"): lambda value: value / 1000,
    ("km", "m"): lambda value: value * 1000,
    ("minute", "second"): lambda value: value * 60,
    ("second", "minute"): lambda value: value / 60,
    ("hour", "minute"): lambda value: value * 60,
    ("minute", "hour"): lambda value: value / 60,
}

UNIT_DISPLAY = {
    "km": ("km", "km"),
    "m": ("meter", "meters"),
    "cm": ("cm", "cm"),
    "mile": ("mile", "miles"),
    "kg": ("kg", "kg"),
    "lb": ("pound", "pounds"),
    "minute": ("minute", "minutes"),
    "second": ("second", "seconds"),
    "hour": ("hour", "hours"),
    "celsius": ("°C", "°C"),
    "fahrenheit": ("°F", "°F"),
}

# -----------------------------
# Prime Check
# -----------------------------

def is_prime(n):
    if n <= 1:
        return False
    if n <= 3:
        return True
    if n % 2 == 0 or n % 3 == 0:
        return False
    i = 5
    while i * i <= n:
        if n % i == 0 or n % (i + 2) == 0:
            return False
        i += 6
    return True


# -----------------------------
# Safe Evaluator
# -----------------------------

def safe_eval(expr: str):
    try:
        expr = expr.replace("^", "**")

        # Convert 15% → (15/100)
        expr = re.sub(r"(\d+)%", r"(\1/100)", expr)

        code = compile(expr, "<string>", "eval")

        for name in code.co_names:
            if name not in ALLOWED_NAMES:
                return None

        result = eval(code, {"__builtins__": {}}, ALLOWED_NAMES)

        # Clean float formatting
        if isinstance(result, float):
            if result.is_integer():
                result = int(result)
            else:
                result = round(result, 6)

        return result

    except:
        return None


def format_numeric(value):
    if isinstance(value, float):
        if value.is_integer():
            return str(int(value))
        return str(round(value, 6))
    return str(value)


def normalize_prompt(prompt: str):
    prompt = prompt.lower().strip()
    prompt = re.sub(r"\s+", " ", prompt)
    return prompt


def normalize_math_prompt(prompt: str):
    prompt = normalize_prompt(prompt)
    prompt = re.sub(
        r"^(what is|calculate|solve|result of|compute|evaluate|convert|can you calculate|can you compute)\s+",
        "",
        prompt,
    )
    prompt = re.sub(r"\bmultiplied by\b", "*", prompt)
    prompt = re.sub(r"\bdivided by\b", "/", prompt)
    prompt = re.sub(r"\btimes\b", "*", prompt)
    prompt = re.sub(r"\bplus\b", "+", prompt)
    prompt = re.sub(r"\bminus\b", "-", prompt)
    prompt = re.sub(r"^square root of\s+(\d+\.?\d*)$", r"sqrt(\1)", prompt)
    prompt = re.sub(r"^sqrt\s+(\d+\.?\d*)$", r"sqrt(\1)", prompt)
    return prompt.strip(" ?.")


def normalize_unit_name(unit: str):
    return UNIT_ALIASES.get(unit.lower().strip(), unit.lower().strip())


def format_unit_label(unit: str, value: float):
    singular, plural = UNIT_DISPLAY.get(unit, (unit, unit))
    return singular if abs(value) == 1 else plural


# -----------------------------
# Unit Conversions
# -----------------------------

def unit_conversion(prompt: str):
    prompt = normalize_prompt(prompt)
    prompt = prompt.replace(" into ", " to ").replace(" in ", " to ")

    conversion_match = re.search(r"(\d+\.?\d*)\s*([a-z°]+)\s+to\s+([a-z°]+)", prompt)
    if not conversion_match:
        return None

    value = float(conversion_match.group(1))
    source_unit = normalize_unit_name(conversion_match.group(2).replace("°", ""))
    target_unit = normalize_unit_name(conversion_match.group(3).replace("°", ""))

    if (source_unit, target_unit) == ("celsius", "fahrenheit"):
        result = round((value * 9 / 5) + 32, 2)
        return f"{format_numeric(value)}°C = {format_numeric(result)}°F"

    if (source_unit, target_unit) == ("fahrenheit", "celsius"):
        result = round((value - 32) * 5 / 9, 2)
        return f"{format_numeric(value)}°F = {format_numeric(result)}°C"

    converter = LINEAR_CONVERSIONS.get((source_unit, target_unit))
    if converter:
        result = converter(value)
        source_label = format_unit_label(source_unit, value)
        target_label = format_unit_label(target_unit, result)
        return f"{format_numeric(value)} {source_label} = {format_numeric(result)} {target_label}"

    return None


# -----------------------------
# Deterministic Entry Point
# -----------------------------

def deterministic_engine(prompt: str):
    prompt = prompt.strip()
    prompt_lower = normalize_prompt(prompt)
    
    # Strip natural language wrappers for math
    math_prompt = normalize_math_prompt(prompt_lower)

    greetings = ["hi", "hello", "hey", "yo", "sup", "good morning", "good evening", "good afternoon", "greetings", "what's up", "how are you", "how's it going", "how do you do", "nice to meet you", "pleased to meet you", "how are you doing", "how have you been", "what's new", "what's going on", "how's everything", "how's life", "how's your day", "how's it going", "how's it hanging","Hey, whats up"]
    if prompt_lower.strip() in greetings:
        return "Hello! How can I help you today?"


    # 1️⃣ Prime check
    prime_match = re.search(r"(?:is\s+)?(\d+)\s+(?:a\s+)?prime(?:\s+number)?", prompt_lower)
    if not prime_match:
        prime_match = re.search(r"check if (\d+) is prime", prompt_lower)
    if prime_match:
        number = int(prime_match.group(1))
        return f"{number} is prime: {is_prime(number)}"

    # 2️⃣ Percentage natural language: "15% of 200"
    percent_of = re.search(r"(\d+)%\s*of\s*(\d+)", prompt_lower)
    if percent_of:
        a = float(percent_of.group(1))
        b = float(percent_of.group(2))
        result = (a / 100) * b
        if result.is_integer():
            result = int(result)
        return f"Result: {result}"

    # 3️⃣ Pure arithmetic detection (must contain at least one digit)
    math_pattern = r"^(?=.*\d)[0-9\.\+\-\*/\(\)%\s\^!<>=&|~]*$"
    if re.fullmatch(math_pattern, math_prompt):
        result = safe_eval(math_prompt)
        if result is not None:
            return f"Result: {result}"
        else:
            return "This mathematical expression appears to be invalid or contains unsupported syntax."

    # 4️⃣ Function-based math detection
    allowed_fns = ["sqrt", "log", "sin", "cos", "tan", "pi", "e", "abs", "round"]
    if any(fn in math_prompt for fn in allowed_fns):
        result = safe_eval(math_prompt)
        if result is not None:
            return f"Result: {result}"
        else:
            stripped = math_prompt
            for fn in allowed_fns:
                stripped = stripped.replace(fn, "")
            math_pattern_extended = r"^[0-9\.\+\-\*/\(\)%\s\^!<>=&|~,]*$"
            if re.fullmatch(math_pattern_extended, stripped):
                return "This mathematical expression appears to be invalid or contains unsupported syntax."

    # 5️⃣ Unit conversion
    conversion = unit_conversion(prompt)
    if conversion:
        return conversion

    return None
