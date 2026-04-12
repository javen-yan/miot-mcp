"""Normalization and low-level matching helpers."""

from typing import Any, Dict, List, Optional


def extract_spec_device_type(device: Dict[str, Any]) -> str:
    spec_type = str(device.get("spec_type", "") or "")
    parts = spec_type.split(":")
    if len(parts) >= 4 and parts[0] == "urn" and parts[1] == "miot-spec-v2" and parts[2] == "device":
        return parts[3]
    return ""


def normalize_home(home: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "home_id": str(home.get("id", "")),
        "name": home.get("name"),
        "owner_uid": home.get("uid"),
        "room_count": len(home.get("roomlist", []) or []),
        "rooms": [
            {
                "room_id": str(room.get("id", "")),
                "name": room.get("name"),
            }
            for room in (home.get("roomlist", []) or [])
        ],
    }


def normalize_scene(scene: Dict[str, Any], home_name: str | None = None) -> Dict[str, Any]:
    return {
        "scene_id": str(scene.get("scene_id") or scene.get("id") or ""),
        "name": scene.get("name"),
        "home_id": str(scene.get("home_id") or ""),
        "home_name": home_name,
    }


def normalize_device(device: Dict[str, Any]) -> Dict[str, Any]:
    home_id = str(device.get("home_id") or "")
    home_name = device.get("home_name")
    room_id = str(device.get("room_id") or "")
    room_name = device.get("room_name")
    device_type = extract_spec_device_type(device)
    split = device.get("extra", {}).get("split", {}) if isinstance(device.get("extra"), dict) else {}
    parent_device_id = str(split.get("parentId") or "")
    control_topology = "subdevice_channel" if parent_device_id else "standalone"
    if device_type == "switch" and control_topology == "subdevice_channel":
        control_semantics = "switch_channel_for_named_load"
    elif device_type == "switch":
        control_semantics = "switch_device"
    elif device_type in {"light", "ceiling-light", "ambient-light", "night-light", "bathroom-light", "light-strip"}:
        control_semantics = "direct_lighting_device"
    else:
        control_semantics = "generic_device"
    return {
        "device_id": str(device.get("did") or ""),
        "name": device.get("name"),
        "model": device.get("model"),
        "device_type": device_type,
        "spec_type": device.get("spec_type"),
        "control_topology": control_topology,
        "control_semantics": control_semantics,
        "parent_device_id": parent_device_id or None,
        "home_id": home_id,
        "home_name": home_name,
        "room_id": room_id,
        "room_name": room_name,
        "location": {
            "home_id": home_id,
            "home_name": home_name,
            "room_id": room_id,
            "room_name": room_name,
            "label": " / ".join([part for part in [home_name, room_name] if part]),
        },
        "online": bool(device.get("isOnline", device.get("online", True))),
    }


def normalize_device_summary(device: Dict[str, Any]) -> Dict[str, Any]:
    normalized = normalize_device(device)
    return {
        "device_id": normalized["device_id"],
        "name": normalized["name"],
        "model": normalized["model"],
        "device_type": normalized["device_type"],
        "control_topology": normalized["control_topology"],
        "control_semantics": normalized["control_semantics"],
        "home_id": normalized["home_id"],
        "room_name": normalized["room_name"],
        "room_id": normalized["room_id"],
        "home_name": normalized["home_name"],
        "location": normalized["location"],
        "online": normalized["online"],
    }


def normalize_property(prop: Any) -> Dict[str, Any]:
    return {
        "name": getattr(prop, "name", None),
        "description": getattr(prop, "desc", None),
        "type": getattr(prop, "type", None),
        "access": getattr(prop, "rw", None),
        "unit": getattr(prop, "unit", None),
        "range": getattr(prop, "range", None),
        "value_list": getattr(prop, "value_list", None),
    }


def normalize_action(action: Any) -> Dict[str, Any]:
    return {
        "name": getattr(action, "name", None),
        "description": getattr(action, "desc", None),
    }


def dedupe_properties(properties: List[Any]) -> List[Any]:
    unique: Dict[str, Any] = {}
    for prop in properties:
        name = getattr(prop, "name", None)
        if not name:
            continue
        unique[name] = prop
    return list(unique.values())


def dedupe_actions(actions: List[Any]) -> List[Any]:
    unique: Dict[str, Any] = {}
    for action in actions:
        name = getattr(action, "name", None)
        if not name:
            continue
        unique[name] = action
    return list(unique.values())


def find_supported_name(names: List[str], aliases: List[str]) -> Optional[str]:
    normalized = {name.lower(): name for name in names}
    for alias in aliases:
        if alias.lower() in normalized:
            return normalized[alias.lower()]
    return None


def is_property_readable(prop: Any) -> bool:
    access = str(getattr(prop, "rw", "") or "").lower()
    return "r" in access or not access


def is_property_writable(prop: Any) -> bool:
    access = str(getattr(prop, "rw", "") or "").lower()
    return "w" in access


def find_supported_property(properties: List[Any], aliases: List[str], writable_only: bool = False) -> Optional[Any]:
    candidates = properties if not writable_only else [prop for prop in properties if is_property_writable(prop)]
    names = [getattr(prop, "name", "") for prop in candidates]
    matched = find_supported_name(names, aliases)
    if not matched:
        return None
    for prop in candidates:
        if getattr(prop, "name", None) == matched:
            return prop
    return None


def find_supported_action(actions: List[Any], aliases: List[str]) -> Optional[Any]:
    names = [getattr(action, "name", "") for action in actions]
    matched = find_supported_name(names, aliases)
    if not matched:
        return None
    for action in actions:
        if getattr(action, "name", None) == matched:
            return action
    return None
