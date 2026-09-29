import json
import re

from pydantic import ValidationError

from app.agent.exceptions import ParseError
from app.models.chat import PackingResponse

_THINKING_TAG_PATTERN = re.compile(
    r"<think>.*?</think>",
    flags=re.DOTALL,
)
_JSON_FENCE_PATTERN = re.compile(
    r"```(?:json)?\s*(.*?)\s*```",
    flags=re.DOTALL | re.IGNORECASE,
)
# Models sometimes emit \u escapes that are not valid 4-hex sequences.
_INVALID_UNICODE_ESCAPE = re.compile(r"\\u(?![0-9a-fA-F]{4})")
_TRAILING_COMMA = re.compile(r",(\s*[}\]])")
# Missing comma before the next object key (newline or same line).
_MISSING_COMMA_BEFORE_KEY = re.compile(
    r'("(?:\\.|[^"\\])*"|true|false|null|-?\d+(?:\.\d+)?)(\s+)"'
)
_MISSING_COMMA_AFTER_CONTAINER = re.compile(r'([}\]])(\s*)"')
_MISSING_COMMA_BETWEEN_CONTAINERS = re.compile(r"([}\]])(\s*)([{\[])")
_TOOL_SHAPED_NAMES = frozenset(
    {"get_weather", "baggage_rules", "traveler_profile", "check_baggage_rules"}
)
_PACKING_KEYS = (
    "destination",
    "packing_items",
    "weather_summary",
    "start_date",
    "end_date",
    "language",
    "rules_disclaimer",
)


def clean_model_output(text: str) -> str:
    return _THINKING_TAG_PATTERN.sub("", text).strip()


def _iter_json_object_spans(text: str) -> list[str]:
    """Return balanced top-level `{...}` slices, respecting JSON strings."""
    objects: list[str] = []
    i = 0
    length = len(text)
    while i < length:
        if text[i] != "{":
            i += 1
            continue
        depth = 0
        in_str = False
        escape = False
        for j in range(i, length):
            ch = text[j]
            if in_str:
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == '"':
                    in_str = False
                continue
            if ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    objects.append(text[i : j + 1])
                    i = j + 1
                    break
        else:
            break
    return objects


def sanitize_json_text(text: str) -> str:
    """Repair common model JSON defects that break json.loads."""
    repaired = _INVALID_UNICODE_ESCAPE.sub(r"\\\\u", text)
    repaired = _TRAILING_COMMA.sub(r"\1", repaired)
    repaired = _MISSING_COMMA_BETWEEN_CONTAINERS.sub(r"\1,\2\3", repaired)
    repaired = _MISSING_COMMA_BEFORE_KEY.sub(r'\1,\2"', repaired)
    repaired = _MISSING_COMMA_AFTER_CONTAINER.sub(r'\1,\2"', repaired)
    return repaired


def _loads_payload(text: str) -> object:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    if "{" in text:
        try:
            from json_repair import loads as repair_loads

            repaired = repair_loads(text)
            if isinstance(repaired, dict):
                return repaired
        except Exception:
            pass

    try:
        return json.loads(sanitize_json_text(text))
    except json.JSONDecodeError as exc:
        raise ParseError(f"Invalid JSON: {exc.msg}") from exc


def _score_packing_candidate(payload: object) -> int:
    if not isinstance(payload, dict):
        return -1
    name = payload.get("name")
    if name in _TOOL_SHAPED_NAMES and "destination" not in payload:
        return -100
    score = 0
    for key in _PACKING_KEYS:
        if key in payload:
            score += 1
    items = payload.get("packing_items")
    if isinstance(items, list) and items:
        score += 3
    return score


def extract_json_text(text: str) -> str:
    cleaned = clean_model_output(text)
    fenced = _JSON_FENCE_PATTERN.search(cleaned)
    if fenced:
        cleaned = fenced.group(1).strip()

    candidates = _iter_json_object_spans(cleaned)
    if not candidates:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1 and end > start:
            return cleaned[start : end + 1]
        return cleaned

    best_text = candidates[0]
    best_score = -1
    for candidate in candidates:
        try:
            payload = _loads_payload(candidate)
        except json.JSONDecodeError:
            continue
        score = _score_packing_candidate(payload)
        if score > best_score:
            best_score = score
            best_text = candidate
    return best_text


def parse_packing_response(text: str) -> PackingResponse:
    extracted = extract_json_text(text)
    try:
        payload = _loads_payload(extracted)
    except ParseError:
        raise
    except Exception as exc:
        raise ParseError(f"Invalid JSON: {exc}") from exc

    if not isinstance(payload, dict):
        raise ParseError("Schema validation failed: expected a JSON object")

    if payload.get("name") in _TOOL_SHAPED_NAMES and "destination" not in payload:
        raise ParseError(
            "Schema validation failed: tool-shaped JSON is not a PackingResponse"
        )

    try:
        return PackingResponse.model_validate(payload)
    except ValidationError as exc:
        raise ParseError(f"Schema validation failed: {exc}") from exc
