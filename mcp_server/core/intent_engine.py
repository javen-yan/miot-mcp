"""Intent parsing engine backed by capability and intent registries."""

import re
from typing import Any, Dict, List, Optional

from mcp_server.device_definitions.intent_definitions import INTENT_REGISTRY
from mcp_server.device_definitions.standard_capabilities import CAPABILITY_REGISTRY, get_capability_definition

CHINESE_NUMERAL_MAP = {
    "一": 1,
    "二": 2,
    "两": 2,
    "三": 3,
    "四": 4,
    "五": 5,
}


def extract_first_int(text: str) -> Optional[int]:
    match = re.search(r"(-?\d+)", text)
    if match:
        return int(match.group(1))
    if "半开" in text or "一半" in text:
        return 50
    level_match = re.search(r"([一二两三四五])\s*[档级]", text)
    if level_match:
        return CHINESE_NUMERAL_MAP.get(level_match.group(1))
    return None


def extract_assignment_value(text: str) -> Optional[str]:
    match = re.search(r"(?:设为|设置为|设置成|调成|调到|调为|切换到|切换为|改成|改为)\s*(.+)$", text)
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
    # Strip leading single-char 开/关 when not part of 开关/开合
    result = re.sub(r"^(?:帮我|请)?\s*(?:开(?!关|合)|关(?!闭|掉|了|上|系))", " ", text.strip())
    patterns = [
        "帮我", "请", "把", "将", "给", "一下", "一下子", "执行",
        "打开", "开启", "开一下", "启动", "亮起", "拉开", "升起",
        "关闭", "关掉", "关了", "关上", "熄灭", "合上", "拉上", "停止",
        "调到", "调成", "调为", "设置为", "设为", "设置成", "切换到", "切换为", "切换", "反转",
        "改成", "改为", "运行", "看看", "查询", "查看", "获取", "的",
    ]
    for pattern in patterns:
        result = result.replace(pattern, " ")
    # Remove standalone numeric tokens with units that were already parsed
    result = re.sub(r"[一二两三四五]\s*[档级]", " ", result)
    result = re.sub(r"-?\d+(?:\.\d+)?\s*(?:%|度|℃|°C|°c|k|K|档)?", " ", result)
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
        "现在状态",
        "当前状态",
        "的状态",
        "状态",
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
    if any(keyword in text for keyword in intent_definition.get("keywords", [])):
        return True
    if intent_name == "turn_on" and re.search(r"^(?:帮我|请)?\s*开(?!关|合)", text.strip()):
        return True
    if intent_name == "turn_off" and re.search(r"^(?:帮我|请)?\s*关(?!闭|掉|了|上)", text.strip()):
        return True
    return False


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

    if capability_name == "brightness" and numeric_value is None:
        if any(w in text for w in ("最亮", "全亮", "最大")):
            return 100
        if any(w in text for w in ("最暗", "最低")):
            return 1
        if any(w in text for w in ("调亮", "亮一点")):
            return 80
        if any(w in text for w in ("调暗", "暗一点")):
            return 30

    if numeric_value is not None:
        return numeric_value

    pattern = definition.get("intent_pattern")
    if pattern:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1)

    assigned_value = extract_assignment_value(text)
    if assigned_value:
        return assigned_value

    if capability_name == "color_temperature":
        if "暖" in text:
            return "暖"
        if "冷" in text:
            return "冷"

    if "intent_default_value" in definition:
        return definition["intent_default_value"]

    cleaned = strip_keywords(text, definition.get("intent_strip_keywords", []))
    return cleaned or None


def parse_operation_intent(text: str, room: str) -> Optional[Dict[str, Any]]:
    # If query is explicitly a status/value inquiry (e.g. "查看空调温度是多少"), route to get_device first
    if any(q in text for q in ("查看", "看看", "查询", "获取", "多少", "几度")) and not any(
        w in text for w in ("调到", "调成", "设为", "设置为", "设置成", "改成", "切换到")
    ):
        device_query = clean_device_query(text, room)
        if not device_query:
            return {"intent": "list_devices", "device_query": "", "room": room}
        return {"intent": "get_device", "device_query": device_query, "room": room}

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
        # Special guard: "%", "k", "K" in brightness/color_temperature require a number unless explicit keyword present
        if capability_name == "brightness" and not any(
            kw in text for kw in ("亮度", "调亮", "调暗", "亮一点", "暗一点", "最亮", "最暗")
        ):
            if extract_first_int(text) is None or "窗帘" in text:
                continue
        if capability_name == "color_temperature" and not any(
            kw in text for kw in ("色温", "冷光", "暖光", "冷白", "暖白")
        ):
            if not re.search(r"\d+\s*[kK]", text):
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
            # Clean specific short phrases like 开灯 -> 灯, 关空调 -> 空调
            normalized_text = (
                text.replace("开灯", "打开 灯")
                .replace("关灯", "关闭 灯")
                .replace("开空调", "打开 空调")
                .replace("关空调", "关闭 空调")
                .replace("开风扇", "打开 风扇")
                .replace("关风扇", "关闭 风扇")
            )
            device_query = clean_device_query(normalized_text, room)
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
