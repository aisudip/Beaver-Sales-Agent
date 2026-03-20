# utils/json_utils.py — JSON parsing utilities for LLM output
import json
from typing import Any, Dict

from utils.logging import get_logger

logger = get_logger(__name__)


def parse_llm_json(output: Any) -> Dict:
    """Parse a JSON object from an LLM string response."""
    # If the output is already a dict, return it directly
    if isinstance(output, dict):
        return output
    
    # If it's something unexpected (e.g., list, None), fail loudly
    if not isinstance(output, str):
        raise TypeError(f"parse_llm_json expected str or dict, got {type(output)}: {output!r}")
    
    # Normal string handling
    output = output.strip()
    start = output.find('{')
    end = output.rfind('}')
    if start == -1 or end == -1:
        raise ValueError(f"No JSON object found in LLM output: {output!r}")

    json_str = output[start:end + 1]

    # First attempt: direct JSON parsing
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        pass

    # Second attempt: handle double-escaped JSON (common LLM quirk)
    if '\\"' in json_str:
        try:
            inner = json.loads(f'"{json_str}"')
            return json.loads(inner)
        except Exception as e2:
            logger.error("Failed to parse double-escaped JSON: %s | Raw: %s", e2, json_str[:200])
            raise ValueError(
                f"Failed to parse double-escaped JSON from LLM output: {e2}\nRaw: {json_str!r}"
            )
        
    # If we get here, it's broken in some other way
    raise ValueError(f"Failed to parse JSON from LLM output: {json_str!r}")


def coerce_payload(payload: Any) -> Dict:
    """Coerce an LLM response (str, dict, or object with .content) into a dict."""
    # If it's already a dict, return as is
    if isinstance(payload, dict):
        return payload
    
    # If it's an object with a .content attribute (e.g., some LLM response types), extract it
    if hasattr(payload, "content"):
        payload = payload.content

    # If it's a string, attempt to parse it as JSON
    if isinstance(payload, str):
        payload = payload.strip()
        try:
            return json.loads(payload)
        except json.JSONDecodeError:
            return {
                "order_id": "0000",
                "requested_items": [],
                "order_context": payload,
                "order_status": "Failed",
                "error": "LLM returned non-JSON or mixed response"
            }

    raise TypeError(f"payload must be dict or JSON string; got {type(payload)}")
