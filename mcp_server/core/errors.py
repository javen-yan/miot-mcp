"""Structured MCP result helpers for the Mijia MCP server."""

import ast
import json
from typing import Any, Dict, List

import mcp.types as types


def serialize_payload(payload: Dict[str, Any]) -> str:
    return json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
    )


def build_result(success: bool, message: str, **extra: Any) -> types.CallToolResult:
    payload = {"success": success, "message": message, **extra}
    return types.CallToolResult(
        content=[types.TextContent(type="text", text=serialize_payload(payload))],
        structuredContent=payload,
        isError=not success,
    )


def build_resource_result(success: bool, message: str, **extra: Any) -> str:
    return serialize_payload({"success": success, "message": message, **extra})


def _parse_candidates_from_message(message: str) -> List[str]:
    marker = "Candidates:"
    if marker not in message:
        return []
    candidate_text = message.split(marker, 1)[1].strip()
    try:
        parsed = ast.literal_eval(candidate_text)
    except (ValueError, SyntaxError):
        return []
    return [str(item) for item in parsed] if isinstance(parsed, list) else []


def classify_error(message: str) -> Dict[str, Any]:
    error = {
        "code": "UNKNOWN_ERROR",
        "category": "unknown",
        "details": message,
        "suggestions": [],
    }

    if "Failed to connect to Mijia cloud service" in message:
        error.update(
            code="CONNECTION_FAILED",
            category="connection",
            suggestions=["Check QR login status", "Try reconnect_service", "Review the local log file for cloud login errors"],
        )
        return error

    if "设备操作超时" in message or "-704083036" in message:
        error.update(
            code="DEVICE_TIMEOUT",
            category="device",
            suggestions=[
                "The device appears to be reachable in the cloud but did not respond in time",
                "Try the same command again after a moment",
                "For wall-switch subchannels, check whether the parent switch or gateway is responding normally",
            ],
        )
        return error

    if "Multiple devices matched" in message:
        error.update(
            code="DEVICE_AMBIGUOUS",
            category="device",
            candidates=_parse_candidates_from_message(message),
            suggestions=["Specify the room", "Specify the home", "Use the exact custom device name"],
        )
        return error

    if "No device matched" in message or "Device with id" in message and "not found" in message:
        error.update(
            code="DEVICE_NOT_FOUND",
            category="device",
            suggestions=["Check the custom device name", "Specify the room or home", "Call list_devices first"],
        )
        return error

    if "Multiple scenes matched" in message:
        error.update(
            code="SCENE_AMBIGUOUS",
            category="scene",
            candidates=_parse_candidates_from_message(message),
            suggestions=["Specify the home", "Use the exact scene name"],
        )
        return error

    if "No scene matched" in message or "Scene with id" in message and "not found" in message:
        error.update(
            code="SCENE_NOT_FOUND",
            category="scene",
            suggestions=["Check the scene name", "Specify the home", "Call list_scenes first"],
        )
        return error

    if "Multiple homes matched" in message:
        error.update(
            code="HOME_AMBIGUOUS",
            category="home",
            suggestions=["Use the exact home name", "Pass home_id instead of home_name"],
        )
        return error

    if "No home matched" in message or "Home with id" in message and "not found" in message:
        error.update(
            code="HOME_NOT_FOUND",
            category="home",
            suggestions=["Check the home name", "Call list_homes first"],
        )
        return error

    if "does not support" in message or "does not expose a writable" in message:
        error.update(
            code="UNSUPPORTED_OPERATION",
            category="capability",
            suggestions=["Call get_device_capabilities first", "Choose one of the supported operations returned by the device profile"],
        )
        return error

    if "is required for" in message:
        error.update(
            code="INVALID_ARGUMENT",
            category="input",
            suggestions=["Pass the required argument explicitly", "Use the higher-level tool when possible instead of control_device"],
        )
        return error

    return error


def build_error_result(exc: Exception, **extra: Any) -> types.CallToolResult:
    message = str(exc)
    error = classify_error(message)
    return build_result(False, message, error=error, **extra)


def extract_structured_content(result: Any) -> Dict[str, Any]:
    if isinstance(result, types.CallToolResult):
        if result.structuredContent is not None:
            return dict(result.structuredContent)
        if result.content:
            first_block = result.content[0]
            if isinstance(first_block, types.TextContent):
                try:
                    parsed = json.loads(first_block.text)
                except json.JSONDecodeError:
                    return {"text": first_block.text}
                return parsed if isinstance(parsed, dict) else {"result": parsed}
        return {}

    if isinstance(result, str):
        try:
            parsed = json.loads(result)
        except json.JSONDecodeError:
            return {"text": result}
        return parsed if isinstance(parsed, dict) else {"result": parsed}

    if isinstance(result, dict):
        return result

    return {"result": result}
