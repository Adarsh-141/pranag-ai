"""
Prompt Parser  (Harshit's LLM layer)

Converts a free-text user prompt into a structured ParsedPrompt dict.

Key fixes over v1:
  • Strips DeepSeek-R1 <think>…</think> CoT blocks before JSON extraction
  • Normalises field aliases ("stress" → "stress_conditions", etc.)
  • Rule-based regex fallback with an Indian-places lookup
  • LLM + regex results are merged field-by-field (best of both)

Bug fixes applied (Jay's audit):
  Fix 1 — _extract_json(): replaced greedy regex r"\{.*\}" with
           brace-counting _find_json_object() so extra LLM text after
           the JSON object does not corrupt json.loads().

  Fix 2 — _regex_fallback(): replaced dead chained .replace() with
           _STRESS_TO_TRAIT dict so "drought stress" → "drought resistance"
           instead of always producing "tolerance".
"""
import json
import re
import logging
import requests

from shared.config import settings

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """You are PRANAG-AI's scientific prompt parser.

Your ONLY job: convert the user prompt into ONE JSON object.
Output NOTHING except the JSON — no markdown fences, no explanation, no <think> tags.

EXACT schema (use these exact key names):
{
  "crop":              string,
  "location":          string,
  "temperature":       number | null,
  "humidity":          number | null,
  "rainfall":          number | null,
  "soil_type":         string | null,
  "stress_conditions": [string],
  "target_traits":     [string],
  "constraints":       {}
}

EXAMPLE
Input:  "wheat for Jodhpur at 48°C with low rainfall"
Output:
{
  "crop": "wheat",
  "location": "Jodhpur, Rajasthan",
  "temperature": 48.0,
  "humidity": null,
  "rainfall": 300,
  "soil_type": "sandy loam",
  "stress_conditions": ["extreme heat stress", "low rainfall", "drought"],
  "target_traits": ["heat tolerance", "drought resistance", "deep root system"],
  "constraints": {}
}
"""

_ALIASES: dict = {
    "stress":          "stress_conditions",
    "stresses":        "stress_conditions",
    "stress_factors":  "stress_conditions",
    "traits":          "target_traits",
    "desired_traits":  "target_traits",
    "target_trait":    "target_traits",
    "temp":            "temperature",
    "temperature_c":   "temperature",
    "temp_celsius":    "temperature",
    "rain":            "rainfall",
    "rainfall_mm":     "rainfall",
    "soil":            "soil_type",
    "place":           "location",
    "region":          "location",
    "city":            "location",
}

_FALLBACK: dict = {
    "crop": "unknown",
    "location": "unknown",
    "temperature": None,
    "humidity": None,
    "rainfall": None,
    "soil_type": None,
    "stress_conditions": [],
    "target_traits": [],
    "constraints": {},
}

_INDIAN_PLACES: list[str] = [
    "punjab", "haryana", "rajasthan", "gujarat", "maharashtra", "karnataka",
    "tamil nadu", "andhra pradesh", "telangana", "madhya pradesh", "uttar pradesh",
    "bihar", "jharkhand", "odisha", "west bengal", "assam", "kerala",
    "himachal pradesh", "uttarakhand", "goa", "delhi", "mumbai", "chennai",
    "kolkata", "bangalore", "bengaluru", "hyderabad", "jodhpur", "jaipur",
    "lucknow", "kanpur", "nagpur", "surat", "ahmedabad", "amritsar", "ludhiana",
    "chandigarh", "patna", "bhopal", "indore", "vadodara", "agra", "varanasi",
    "meerut", "nashik", "coimbatore", "madurai", "vijayawada", "barmer",
    "bikaner", "sikar", "kota", "ajmer", "udaipur", "dehradun", "shimla",
]


def _strip_think_tags(text: str) -> str:
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


def _normalise_keys(raw: dict) -> dict:
    return {_ALIASES.get(k.lower(), k.lower()): v for k, v in raw.items()}


def _find_json_object(text: str) -> str | None:
    """
    FIX 1 — Brace-counting JSON extractor.

    Replaces re.search(r"\{.*\}", text, re.DOTALL) which was greedy and
    captured too much when the LLM added extra text after the JSON object.

    Walks character by character, tracking open/close brace depth,
    and returns exactly the first complete JSON object.
    """
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    for i, ch in enumerate(text[start:], start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start: i + 1]
    return None


def _extract_json(text: str) -> dict:
    text = _strip_think_tags(text)
    text = re.sub(r"```(?:json)?", "", text).strip().rstrip("`").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    match = _find_json_object(text)
    if not match:
        raise ValueError(f"No JSON object in LLM output:\n{text[:400]}")
    return json.loads(match)


_STRESS_KEYWORDS: dict = {
    "heat stress":     ["heat", "hot", "temperature", "degree", "celsius", "thermal"],
    "drought stress":  ["drought", "dry", "low rainfall", "arid", "water stress"],
    "salinity stress": ["saline", "salinity", "salt", "alkaline"],
    "cold stress":     ["cold", "frost", "freeze", "winter"],
    "flood stress":    ["flood", "waterlog", "submerge"],
}

_TRAIT_MAP: dict = {
    "heat tolerance":     ["heat", "hot", "high temperature", "degree", "celsius"],
    "drought resistance": ["drought", "dry", "low rainfall", "water"],
    "salinity tolerance": ["saline", "salt", "alkaline"],
    "high yield":         ["yield", "productive", "output"],
    "disease resistance": ["disease", "fungal", "rust", "blight"],
}

# FIX 2 — Stress-to-trait lookup dict.
# Replaces the dead chained .replace() which always produced "tolerance"
# and never "resistance" because the first replace consumed " stress".
_STRESS_TO_TRAIT: dict = {
    "heat stress":     "heat tolerance",
    "drought stress":  "drought resistance",
    "salinity stress": "salinity tolerance",
    "cold stress":     "cold tolerance",
    "flood stress":    "flood tolerance",
}

_TEMP_RE = re.compile(r"(\d{1,3}(?:\.\d+)?)\s*(?:degree[s]?\s*)?°?\s*[cC](?:elsius)?")
_DEG_RE  = re.compile(r"(\d{2,3})\s*degree")
_HUM_RE  = re.compile(r"(\d{1,3})\s*%\s*humidity")
_RAIN_RE = re.compile(r"(\d{2,4})\s*mm")

_CROPS: list[str] = [
    "wheat", "rice", "maize", "corn", "barley", "sorghum", "millet",
    "soybean", "cotton", "mustard", "chickpea", "lentil", "bajra",
    "jowar", "groundnut", "sugarcane", "potato", "tomato", "oat",
]


def _extract_location(prompt: str) -> str:
    p = prompt.lower()
    matched = [place for place in _INDIAN_PLACES if place in p]
    if matched:
        return max(matched, key=len).title()
    m = re.search(
        r"(?:in|for|at|from|near)\s+([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)", prompt
    )
    return m.group(1).strip() if m else "unknown"


def _regex_fallback(prompt: str) -> dict:
    p = prompt.lower()

    temp_match  = _TEMP_RE.search(prompt) or _DEG_RE.search(p)
    temperature = float(temp_match.group(1)) if temp_match else None

    hum_match  = _HUM_RE.search(p)
    rain_match = _RAIN_RE.search(p)
    humidity   = float(hum_match.group(1))  if hum_match  else None
    rainfall   = float(rain_match.group(1)) if rain_match else None

    stresses = [s for s, kws in _STRESS_KEYWORDS.items() if any(kw in p for kw in kws)]
    if not stresses and temperature and temperature >= 38:
        stresses = ["heat stress"]

    traits = [t for t, kws in _TRAIT_MAP.items() if any(kw in p for kw in kws)]
    if not traits and stresses:
        # FIX 2: use lookup dict instead of broken chained replace
        traits = [
            _STRESS_TO_TRAIT.get(s, s.replace(" stress", " tolerance"))
            for s in stresses
        ]

    return {
        "crop":              next((c for c in _CROPS if c in p), "unknown"),
        "location":          _extract_location(prompt),
        "temperature":       temperature,
        "humidity":          humidity,
        "rainfall":          rainfall,
        "soil_type":         None,
        "stress_conditions": stresses,
        "target_traits":     traits,
        "constraints":       {},
        "_source":           "regex_fallback",
    }


# def parse_prompt(user_prompt: str) -> dict:
#     """
#     Strategy:
#     1. Regex fallback runs immediately (fast, no network, always works).
#     2. LLM called via Ollama; on success its non-empty fields override regex.
#     3. Merged result: every field is the best available value.
#     """
#     regex_result = _regex_fallback(user_prompt)
#     base = {**_FALLBACK, **regex_result}

#     try:
#         payload = {
#             "model":  settings.ollama_model,
#             "stream": False,
#             "messages": [
#                 {"role": "system", "content": _SYSTEM_PROMPT},
#                 {"role": "user",   "content": f"Parse this prompt:\n\n{user_prompt}"},
#             ],
#         }
#         resp = requests.post(
#             f"{settings.ollama_base_url}/api/chat",
#             json=payload,
#             timeout=settings.ollama_timeout,
#         )
#         resp.raise_for_status()
#         raw_text = resp.json().get("message", {}).get("content", "")

#         if raw_text:
#             llm_result = _normalise_keys(_extract_json(raw_text))
#             for key in _FALLBACK:
#                 val = llm_result.get(key)
#                 if val not in (None, "", "unknown", [], {}):
#                     base[key] = val
#             logger.info("[prompt_parser] LLM merge applied.")
#         else:
#             logger.warning("[prompt_parser] Empty LLM response — regex only.")

#     except requests.exceptions.ConnectionError:
#         logger.warning("[prompt_parser] Ollama not reachable — regex fallback only.")
#     except requests.exceptions.Timeout:
#         logger.warning("[prompt_parser] Ollama timed out — regex fallback only.")
#     except (ValueError, json.JSONDecodeError, KeyError) as exc:
#         logger.warning("[prompt_parser] LLM output unparseable (%s) — regex used.", exc)

#     base.pop("_source", None)
#     logger.info("[prompt_parser] Final: %s", base)
#     return base

def parse_prompt(user_prompt: str) -> dict:
    """
    Strategy:
    1. Regex fallback runs immediately (fast, no network, always works).
    2. LLM called via OpenRouter; on success its non-empty fields override regex.
    3. Merged result: every field is the best available value.
    """
    regex_result = _regex_fallback(user_prompt)
    base = {**_FALLBACK, **regex_result}

    try:
        headers = {
            "Authorization": f"Bearer {settings.openrouter_api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": settings.openrouter_model,
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user",   "content": f"Parse this prompt:\n\n{user_prompt}"},
            ],
            # Forces the model to return valid JSON
            "response_format": {"type": "json_object"} ,
            "max_tokens": 1000,  # Limit tokens to reduce cost and latency
        }
        
        resp = requests.post(
            f"{settings.openrouter_base_url}/chat/completions",
            headers=headers,
            json=payload,
            timeout=settings.llm_timeout,
        )
        resp.raise_for_status()
        
        # OpenRouter/OpenAI JSON structure parsing
        raw_text = resp.json().get("choices", [{}])[0].get("message", {}).get("content", "")

        if raw_text:
            llm_result = _normalise_keys(_extract_json(raw_text))
            for key in _FALLBACK:
                val = llm_result.get(key)
                if val not in (None, "", "unknown", [], {}):
                    base[key] = val
            logger.info("[prompt_parser] LLM merge applied.")
        else:
            logger.warning("[prompt_parser] Empty LLM response — regex only.")

    except requests.exceptions.ConnectionError:
        logger.warning("[prompt_parser] API not reachable — regex fallback only.")
    except requests.exceptions.HTTPError as exc:
        logger.error("[prompt_parser] OpenRouter HTTP Error: %s", exc.response.text)
    except requests.exceptions.Timeout:
        logger.warning("[prompt_parser] API timed out — regex fallback only.")
    except (ValueError, json.JSONDecodeError, KeyError) as exc:
        logger.warning("[prompt_parser] LLM output unparseable (%s) — regex used.", exc)

    base.pop("_source", None)
    logger.info("[prompt_parser] Final: %s", base)
    return base