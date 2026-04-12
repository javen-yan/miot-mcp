"""Intent parsing engine backed by capability and intent registries."""

import re
from typing import Any, Dict, List, Optional

from mcp_server.device_definitions.intent_definitions import INTENT_REGISTRY
from mcp_server.device_definitions.standard_capabilities import CAPABILITY_REGISTRY, get_capability_definition


def extract_first_int(text: str) -> Optional[int]:
    match = re.search(r"(-?\d+)", text)
    return int(match.group(1)) if match else None


def extract_assignment_value(text: str) -> Optional[str]:
    match = re.search(r"(?:设为|设置为|设置成|调成|调到|切换到|改成)\s*(.+)$", text)
    if not match:
        return None
    value = " ".join(match.group(1).split())
    return value or None


def extract_room_hint(text: str, fallback_room_hints: List[str], known_rooms: Optional[List[str]] = None) -> str:
    room_candidates = []
    if known_rooms:
        room_candidates.extend(
            sorted(
                {room.strip() for room in known_rooms if room and room.strip()},
                key=len,
                reverse=True,
            )
        )
    room_candidates.extend([room for room in fallback_room_hints if room not in room_candidates])

    for room in room_candidates:
        if room in text:
            return room
    return ""


def strip_common_verbs(text: str) -> str:
    patterns = [
        "帮我", "请", "把", "将", "给", "一下", "一下子", "执行", "打开", "关闭", "关掉", "开启",
        "调到", "调成", "设置为", "设为", "设置成", "切换", "运行", "启动", "看看", "查询", "获取",
    ]
    result = text
    for pattern in patterns:
        result = result.replace(pattern, " ")
    return " ".join(result.split())


def strip_room_from_text(text: str, room: str) -> str:
    if not room:
        return text
    return " ".join(text.replace(room, " ").split())


def strip_inventory_phrases(text: str) -> str:
    patterns = [
        "有什么设备",
        "有哪些设备",
        "有啥设备",
        "设备有哪些",
        "设备有什么",
        "什么设备",
        "哪些设备",
        "设备信息",
        "设备情况",
        "有哪些",
        "有什么",
        "有啥",
        "设备",
    ]
    result = text
    for pattern in patterns:
        result = result.replace(pattern, " ")
    return " ".join(result.split())


def matches_intent_keywords(text: str, intent_name: str) -> bool:
    intent_definition = INTENT_REGISTRY.get(intent_name, {})
    return any(keyword in text for keyword in intent_definition.get("keywords", []))


def matches_capability_intent(text: str, capability_name: str) -> bool:
    definition = get_capability_definition(capability_name)
    return any(keyword in text for keyword in definition.get("intent_keywords", []))


def strip_keywords(text: str, keywords: List[str]) -> str:
    result = text
    for keyword in keywords:
        result = result.replace(keyword, " ")
    return strip_common_verbs(result)


def clean_device_query(text: str, room: str = "") -> str:
    result = strip_common_verbs(text)
    result = strip_room_from_text(result, room)
    result = strip_inventory_phrases(result)
    return " ".join(result.split())


def parse_capability_intent_value(text: str, capability_name: str) -> Any:
    definition = get_capability_definition(capability_name)
    numeric_value = extract_first_int(text)

    if definition.get("intent_requires_number") and numeric_value is None:
        return None
    if numeric_value is not None:
        return numeric_value

    assigned_value = extract_assignment_value(text)
    if assigned_value:
        return assigned_value

    if capability_name == "color_temperature":
        if "暖" in text:
            return "暖"
        if "冷" in text:
            return "冷"

    pattern = definition.get("intent_pattern")
    if pattern:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1)

    if "intent_default_value" in definition:
        return definition["intent_default_value"]

    cleaned = strip_keywords(text, definition.get("intent_strip_keywords", []))
    return cleaned or None


def parse_operation_intent(text: str, room: str) -> Optional[Dict[str, Any]]:
    capability_intents = sorted(
        (
            (capability_name, definition)
            for capability_name, definition in CAPABILITY_REGISTRY.items()
            if definition.get("kind") == "property"
            and definition.get("intent_keywords")
            and str(definition.get("preferred_tool", "")).startswith("set_")
        ),
        key=lambda item: item[1].get("intent_priority", 100),
    )

    for capability_name, definition in capability_intents:
        if not matches_capability_intent(text, capability_name):
            continue
        value = parse_capability_intent_value(text, capability_name)
        if definition.get("intent_requires_number") and value is None:
            continue
        stripped_text = strip_keywords(text, definition.get("intent_strip_keywords", []))
        if value is not None and isinstance(value, str):
            stripped_text = stripped_text.replace(value, " ")
        return {
            "intent": definition["preferred_tool"],
            "value": value,
            "device_query": clean_device_query(stripped_text, room),
            "room": room,
        }

    for intent_name, intent_definition in INTENT_REGISTRY.items():
        if intent_definition.get("kind") not in {"operation", "query"}:
            continue
        if matches_intent_keywords(text, intent_name):
            device_query = clean_device_query(text, room)
            if intent_name == "get_device" and not device_query:
                return {
                    "intent": "list_devices",
                    "device_query": "",
                    "room": room,
                }
            return {
                "intent": intent_name,
                "device_query": device_query,
                "room": room,
            }

    return None


def infer_intent(query: str, fallback_room_hints: List[str], known_rooms: Optional[List[str]] = None) -> Dict[str, Any]:
    text = query.strip()
    room = extract_room_hint(text, fallback_room_hints=fallback_room_hints, known_rooms=known_rooms)

    if matches_intent_keywords(text, "execute_scene"):
        scene_name = strip_keywords(text, INTENT_REGISTRY["execute_scene"].get("strip_keywords", []))
        if not scene_name:
            scene_name = text
        return {"intent": "execute_scene", "scene_name": scene_name, "room": room}

    parsed_operation = parse_operation_intent(text, room)
    if parsed_operation:
        return parsed_operation

    return {
        "intent": "list_devices",
        "device_query": clean_device_query(text, room),
        "room": room,
    }
