"""Normalization and low-level matching helpers."""

import re
from typing import Any, Dict, List, Optional


def extract_spec_device_type(device: Dict[str, Any]) -> str:
    spec_type = str(device.get("spec_type", "") or "")
    parts = spec_type.split(":")
    if len(parts) >= 4 and parts[0] == "urn" and parts[1] == "miot-spec-v2" and parts[2] == "device":
        return parts[3]
    return ""


def extract_channel_siid(device: Dict[str, Any]) -> Optional[int]:
    """Extract target service instance ID (siid) for split sub-devices (e.g. did='12345.s2')."""
    did = str(device.get("did") or device.get("device_id") or "")
    match = re.search(r"\.s(\d+)$", did)
    if match:
        return int(match.group(1))
    extra = device.get("extra")
    if isinstance(extra, dict):
        split = extra.get("split")
        if isinstance(split, dict):
            for key in ("siid", "switchId", "channel"):
                val = split.get(key)
                if isinstance(val, int) or (isinstance(val, str) and val.isdigit()):
                    return int(val)
    return None


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
    channel_siid = extract_channel_siid(device)
    control_topology = "subdevice_channel" if (parent_device_id or channel_siid is not None) else "standalone"
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
        "channel_siid": channel_siid,
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
        "spec_type": normalized["spec_type"],
        "control_topology": normalized["control_topology"],
        "control_semantics": normalized["control_semantics"],
        "home_id": normalized["home_id"],
        "room_name": normalized["room_name"],
        "room_id": normalized["room_id"],
        "home_name": normalized["home_name"],
        "location": normalized["location"],
        "online": normalized["online"],
    }


def _get_method_tuple(item: Any, iid_key: str = "piid") -> tuple[int, int]:
    method = getattr(item, "method", None)
    if isinstance(method, dict):
        return int(method.get("siid", 999)), int(method.get(iid_key, 999))
    return (999, 999)


def normalize_property(prop: Any) -> Dict[str, Any]:
    method = getattr(prop, "method", None)
    return {
        "name": getattr(prop, "name", None),
        "description": getattr(prop, "desc", None),
        "type": getattr(prop, "type", None),
        "access": getattr(prop, "rw", None),
        "unit": getattr(prop, "unit", None),
        "range": getattr(prop, "range", None),
        "value_list": getattr(prop, "value_list", None),
        "siid": method.get("siid") if isinstance(method, dict) else None,
        "piid": method.get("piid") if isinstance(method, dict) else None,
    }


def normalize_action(action: Any) -> Dict[str, Any]:
    method = getattr(action, "method", None)
    return {
        "name": getattr(action, "name", None),
        "description": getattr(action, "desc", None),
        "siid": method.get("siid") if isinstance(method, dict) else None,
        "aiid": method.get("aiid") if isinstance(method, dict) else None,
    }


def dedupe_properties(properties: List[Any]) -> List[Any]:
    unique: Dict[str, Any] = {}
    for prop in properties:
        name = getattr(prop, "name", None)
        if not name:
            continue
        if name in unique:
            if _get_method_tuple(prop, "piid") >= _get_method_tuple(unique[name], "piid"):
                continue
        unique[name] = prop
    return sorted(unique.values(), key=lambda p: _get_method_tuple(p, "piid"))


def dedupe_actions(actions: List[Any]) -> List[Any]:
    unique: Dict[str, Any] = {}
    for action in actions:
        name = getattr(action, "name", None)
        if not name:
            continue
        if name in unique:
            if _get_method_tuple(action, "aiid") >= _get_method_tuple(unique[name], "aiid"):
                continue
        unique[name] = action
    return sorted(unique.values(), key=lambda a: _get_method_tuple(a, "aiid"))


def _matches_alias(name: str, alias: str) -> bool:
    name_lower = name.lower()
    alias_lower = alias.lower()
    if name_lower == alias_lower or name_lower == alias_lower.replace("-", "_"):
        return True
    # Match mijiaAPI._deduplicate_names pattern: {alias}-{siid} or {alias}-{siid}-{piid}
    pattern = rf"^{re.escape(alias_lower)}[-_]\d+(?:[-_]\d+)?$"
    if re.match(pattern, name_lower):
        return True
    return False


def find_supported_name(names: List[str], aliases: List[str]) -> Optional[str]:
    normalized = {name.lower(): name for name in names if name}
    for alias in aliases:
        alias_lower = alias.lower()
        if alias_lower in normalized:
            return normalized[alias_lower]
        underscore_alias = alias_lower.replace("-", "_")
        if underscore_alias in normalized:
            return normalized[underscore_alias]
        for name_lower, original_name in normalized.items():
            if _matches_alias(name_lower, alias_lower):
                return original_name
    return None


def is_property_readable(prop: Any) -> bool:
    access = str(getattr(prop, "rw", "") or "").lower()
    return "r" in access or not access


def is_property_writable(prop: Any) -> bool:
    access = str(getattr(prop, "rw", "") or "").lower()
    return "w" in access


def find_supported_property(
    properties: List[Any],
    aliases: List[str],
    writable_only: bool = False,
    preferred_siid: Optional[int] = None,
    expected_type: Optional[str] = None,
) -> Optional[Any]:
    candidates = properties if not writable_only else [prop for prop in properties if is_property_writable(prop)]
    if expected_type == "boolean":
        bool_candidates = [prop for prop in candidates if str(getattr(prop, "type", "")).lower() == "bool"]
        if bool_candidates:
            candidates = bool_candidates

    def sort_key(prop: Any) -> tuple[int, int, int]:
        siid, piid = _get_method_tuple(prop, "piid")
        siid_priority = 0 if (preferred_siid is not None and siid == preferred_siid) else 1
        return (siid_priority, siid, piid)

    sorted_candidates = sorted(candidates, key=sort_key)

    for alias in aliases:
        # 1. If preferred_siid is given, check for exact siid-suffixed match first (e.g., on-3 for siid=3)
        if preferred_siid is not None:
            for prop in sorted_candidates:
                prop_name = str(getattr(prop, "prop_name", None) or getattr(prop, "name", "") or "")
                siid, _ = _get_method_tuple(prop, "piid")
                if siid == preferred_siid and _matches_alias(prop_name, alias):
                    return prop

        # 2. Check exact name match
        for prop in sorted_candidates:
            prop_name = str(getattr(prop, "name", "") or "")
            if prop_name.lower() in {alias.lower(), alias.lower().replace("-", "_")}:
                return prop

        # 3. Check deduplicated name match (e.g., on-2, mode-2, brightness-2)
        for prop in sorted_candidates:
            prop_name = str(getattr(prop, "name", "") or "")
            if _matches_alias(prop_name, alias):
                return prop

    return None


def find_supported_action(
    actions: List[Any],
    aliases: List[str],
    preferred_siid: Optional[int] = None,
) -> Optional[Any]:
    def sort_key(action: Any) -> tuple[int, int, int]:
        siid, aiid = _get_method_tuple(action, "aiid")
        siid_priority = 0 if (preferred_siid is not None and siid == preferred_siid) else 1
        return (siid_priority, siid, aiid)

    sorted_actions = sorted(actions, key=sort_key)

    for alias in aliases:
        if preferred_siid is not None:
            for action in sorted_actions:
                act_name = str(getattr(action, "name", "") or "")
                siid, _ = _get_method_tuple(action, "aiid")
                if siid == preferred_siid and _matches_alias(act_name, alias):
                    return action

        for action in sorted_actions:
            act_name = str(getattr(action, "name", "") or "")
            if act_name.lower() in {alias.lower(), alias.lower().replace("-", "_")}:
                return action

        for action in sorted_actions:
            act_name = str(getattr(action, "name", "") or "")
            if _matches_alias(act_name, alias):
                return action

    return None
