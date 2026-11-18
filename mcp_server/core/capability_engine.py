"""Capability profile and value resolution engine."""

from typing import Any, Dict, List, Optional

from mcp_server.core.normalizers import (
    extract_channel_siid,
    find_supported_action,
    find_supported_name,
    find_supported_property,
    is_property_readable,
    is_property_writable,
    normalize_action,
    normalize_property,
)
from mcp_server.device_definitions.standard_capabilities import (
    CAPABILITY_REGISTRY,
    OPERATION_CAPABILITY_MAP,
    get_capability_definition,
    to_client_tool_name,
)


def extract_device_type(device: Dict[str, Any]) -> str:
    spec_type = str(device.get("spec_type", "") or "")
    parts = spec_type.split(":")
    if len(parts) >= 4 and parts[0] == "urn" and parts[1] == "miot-spec-v2" and parts[2] == "device":
        return parts[3]
    return ""


def capability_matches_device(definition: Dict[str, Any], device: Dict[str, Any]) -> bool:
    supported_device_types = definition.get("supported_device_types", [])
    if not supported_device_types:
        return True
    device_type = extract_device_type(device)
    return not device_type or device_type in supported_device_types


def infer_device_domains(device: Dict[str, Any], properties: List[Any], actions: List[Any]) -> List[str]:
    primary_domains: List[str] = []
    fallback_domains: List[str] = []
    preferred_siid = extract_channel_siid(device)

    for capability_name, definition in CAPABILITY_REGISTRY.items():
        capability_domains = definition.get("domains", [])
        if not capability_domains:
            continue
        matched = False
        if definition["kind"] == "property":
            matched = (
                find_supported_property(
                    properties,
                    definition["aliases"],
                    preferred_siid=preferred_siid,
                    expected_type=definition.get("value_type"),
                )
                is not None
            )
        elif definition["kind"] == "action":
            matched = find_supported_action(actions, definition["aliases"], preferred_siid=preferred_siid) is not None
        if not matched:
            continue

        target_list = primary_domains if capability_matches_device(definition, device) else fallback_domains
        for domain in capability_domains:
            if domain not in primary_domains and domain not in fallback_domains:
                target_list.append(domain)

    domains = primary_domains + [d for d in fallback_domains if d not in primary_domains]
    return domains or ["generic"]


def get_capability_target(prop: Any, target_kind: str) -> Dict[str, Any]:
    method = getattr(prop, "method", None)
    return {
        "kind": "property",
        "capability": target_kind,
        "name": getattr(prop, "name", None),
        "description": getattr(prop, "desc", None),
        "readable": is_property_readable(prop),
        "writable": is_property_writable(prop),
        "type": getattr(prop, "type", None),
        "unit": getattr(prop, "unit", None),
        "range": getattr(prop, "range", None),
        "value_list": getattr(prop, "value_list", None),
        "siid": method.get("siid") if isinstance(method, dict) else None,
        "piid": method.get("piid") if isinstance(method, dict) else None,
    }


def get_action_target(action: Any, target_kind: str) -> Dict[str, Any]:
    method = getattr(action, "method", None)
    return {
        "kind": "action",
        "capability": target_kind,
        "name": getattr(action, "name", None),
        "description": getattr(action, "desc", None),
        "siid": method.get("siid") if isinstance(method, dict) else None,
        "aiid": method.get("aiid") if isinstance(method, dict) else None,
    }


def build_device_capability_profile(device: Dict[str, Any], properties: List[Any], actions: List[Any]) -> Dict[str, Any]:
    controls: Dict[str, Dict[str, Any]] = {}
    preferred_siid = extract_channel_siid(device)

    for capability_name, definition in CAPABILITY_REGISTRY.items():
        if definition["kind"] == "property":
            prop = find_supported_property(
                properties,
                definition["aliases"],
                writable_only=True,
                preferred_siid=preferred_siid,
                expected_type=definition.get("value_type"),
            )
            if prop:
                controls[capability_name] = get_capability_target(prop, capability_name)
        elif definition["kind"] == "action":
            action = find_supported_action(
                actions,
                definition["aliases"],
                preferred_siid=preferred_siid,
            )
            if action:
                controls[capability_name] = get_action_target(action, capability_name)

    device_domains = infer_device_domains(device, properties, actions)
    supported_operations = {}
    for operation_name, capability_name in OPERATION_CAPABILITY_MAP.items():
        if operation_name == "toggle":
            supported_operations[operation_name] = "toggle" in controls or "power" in controls
        elif operation_name in {"turn_on", "turn_off"}:
            supported_operations[operation_name] = (
                "power" in controls
                or "motor_control" in controls
                or "cover_position" in controls
            )
        else:
            supported_operations[operation_name] = capability_name in controls
    supported_operations["set_property"] = any(is_property_writable(prop) for prop in properties)
    supported_operations["run_action"] = bool(actions)

    capability_families: List[str] = []
    for capability_name in controls:
        for family in get_capability_definition(capability_name).get("families", []):
            if family not in capability_families:
                capability_families.append(family)
    if "power" in controls and "toggleable" not in capability_families:
        capability_families.append("toggleable")

    return {
        "device_domains": device_domains,
        "primary_domain": device_domains[0],
        "capability_families": capability_families,
        "controls": controls,
        "supported_operations": supported_operations,
        "properties": [normalize_property(prop) for prop in properties],
        "actions": [normalize_action(action) for action in actions],
    }


def build_profile_driven_schema(properties: List[Any], actions: List[Any]) -> Dict[str, Any]:
    def split_terms(*values: Any) -> List[str]:
        terms: List[str] = []
        for value in values:
            if not value:
                continue
            text = str(value)
            for chunk in text.replace("|", "/").split("/"):
                term = chunk.strip()
                if term and term not in terms:
                    terms.append(term)
        return terms

    property_controls: List[Dict[str, Any]] = []
    for prop in properties:
        normalized = normalize_property(prop)
        matching_terms = split_terms(normalized.get("name"), normalized.get("description"))
        for item in normalized.get("value_list") or []:
            matching_terms.extend(
                term
                for term in split_terms(
                    item.get("description"),
                    item.get("desc"),
                    item.get("desc_zh_cn"),
                    item.get("name"),
                    item.get("value"),
                )
                if term not in matching_terms
            )
        property_controls.append(
            {
                **normalized,
                "readable": is_property_readable(prop),
                "writable": is_property_writable(prop),
                "matching_terms": matching_terms,
                "operation": "set_property" if is_property_writable(prop) else "read_property",
            }
        )

    action_controls: List[Dict[str, Any]] = []
    for action in actions:
        normalized = normalize_action(action)
        action_controls.append(
            {
                **normalized,
                "matching_terms": split_terms(normalized.get("name"), normalized.get("description")),
                "operation": "run_action",
            }
        )

    writable_properties = [item for item in property_controls if item.get("writable")]
    readable_properties = [item for item in property_controls if item.get("readable")]

    return {
        "strategy": "Prefer standard capabilities first. Fall back to control_device(operation='set_property'|'run_action') using the raw profile names below.",
        "generic_operations": {
            "set_property": bool(writable_properties),
            "run_action": bool(action_controls),
        },
        "writable_properties": writable_properties,
        "readable_properties": readable_properties,
        "actions": action_controls,
    }


def build_capability_mapping_report(properties: List[Any], actions: List[Any], capability_profile: Dict[str, Any]) -> Dict[str, Any]:
    mapped_property_names = {
        target.get("name")
        for target in capability_profile.get("controls", {}).values()
        if target.get("kind") == "property" and target.get("name")
    }
    mapped_action_names = {
        target.get("name")
        for target in capability_profile.get("controls", {}).values()
        if target.get("kind") == "action" and target.get("name")
    }

    property_items = [normalize_property(prop) for prop in properties]
    action_items = [normalize_action(action) for action in actions]

    mapped_properties = [item for item in property_items if item.get("name") in mapped_property_names]
    unmapped_properties = [item for item in property_items if item.get("name") not in mapped_property_names]
    mapped_actions = [item for item in action_items if item.get("name") in mapped_action_names]
    unmapped_actions = [item for item in action_items if item.get("name") not in mapped_action_names]

    writable_unmapped_properties = [item for item in unmapped_properties if "w" in str(item.get("access", "")).lower()]
    readable_unmapped_properties = [item for item in unmapped_properties if "r" in str(item.get("access", "")).lower()]

    return {
        "mapped_property_count": len(mapped_properties),
        "unmapped_property_count": len(unmapped_properties),
        "mapped_action_count": len(mapped_actions),
        "unmapped_action_count": len(unmapped_actions),
        "mapped_properties": mapped_properties,
        "unmapped_properties": unmapped_properties,
        "mapped_actions": mapped_actions,
        "unmapped_actions": unmapped_actions,
        "writable_unmapped_properties": writable_unmapped_properties,
        "readable_unmapped_properties": readable_unmapped_properties,
        "coverage": {
            "properties": round(len(mapped_properties) / len(property_items), 3) if property_items else 1.0,
            "actions": round(len(mapped_actions) / len(action_items), 3) if action_items else 1.0,
        },
    }


def coerce_boolean_value(value: Any) -> Any:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        if value == 1:
            return True
        if value == 0:
            return False
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "on", "open", "yes", "打开", "开启", "开"}:
            return True
        if normalized in {"false", "0", "off", "close", "no", "关闭", "关掉", "关", "关上"}:
            return False
    return value


def coerce_enum_value(target: Dict[str, Any], value: Any, definition: Optional[Dict[str, Any]] = None) -> tuple[Any, bool]:
    """Resolve value against target value_list. Returns (resolved_value, matched_bool)."""
    value_list = target.get("value_list") or []
    if not value_list:
        return value, False

    # 1. Exact value match (including type)
    for item in value_list:
        if value == item.get("value") and type(value) is type(item.get("value")):
            return item.get("value"), True

    normalized_input = str(value).strip().lower()
    if not normalized_input:
        return value, False

    # 2. Stringified value match (e.g. "0" -> 0)
    for item in value_list:
        if normalized_input == str(item.get("value", "")).strip().lower():
            return item.get("value"), True

    # Collect all candidate search terms from semantic_inputs if defined
    search_terms = [normalized_input]
    semantic_inputs = (definition or {}).get("semantic_inputs", {})
    for semantic_key, aliases in semantic_inputs.items():
        lowered_aliases = [str(alias).strip().lower() for alias in aliases] + [str(semantic_key).strip().lower()]
        if normalized_input in lowered_aliases:
            for term in lowered_aliases:
                if term and term not in search_terms:
                    search_terms.append(term)

    def _item_labels(item: Dict[str, Any]) -> List[str]:
        raw_labels = [
            item.get("description"),
            item.get("desc"),
            item.get("desc_zh_cn"),
            item.get("desc_en"),
            item.get("name"),
        ]
        labels: List[str] = []
        for raw in raw_labels:
            if not raw:
                continue
            text = str(raw).strip().lower()
            if text:
                labels.append(text)
            for part in text.replace("|", "/").split("/"):
                part_clean = part.strip()
                if part_clean and part_clean not in labels:
                    labels.append(part_clean)
        return labels

    # 3. Exact label match against any search term
    for term in search_terms:
        for item in value_list:
            if term in _item_labels(item):
                return item.get("value"), True

    # 4. Substring label match against any search term
    for term in search_terms:
        if len(term) < 2 and term.isascii():
            continue
        for item in value_list:
            for label in _item_labels(item):
                if term in label or label in term:
                    return item.get("value"), True

    return value, False


def coerce_range_value(target: Dict[str, Any], value: Any, definition: Optional[Dict[str, Any]] = None) -> Any:
    value_range = target.get("range")
    if not (isinstance(value_range, list) and len(value_range) >= 2):
        return value

    prop_type = str(target.get("type") or "").lower()
    minimum = value_range[0]
    maximum = value_range[1]
    step = value_range[2] if len(value_range) >= 3 else None

    # Handle semantic strings like "暖" / "冷" on range-based color temperature
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"暖", "暖光", "暖白", "warm"}:
            value = minimum
        elif lowered in {"冷", "冷光", "冷白", "cool", "cold"}:
            value = maximum

    try:
        numeric_value = float(value)
    except (TypeError, ValueError):
        return value

    clamped = max(float(minimum), min(float(maximum), numeric_value))

    if prop_type == "float":
        if step and step > 0:
            steps = round((clamped - float(minimum)) / float(step))
            clamped = float(minimum) + steps * float(step)
            clamped = max(float(minimum), min(float(maximum), round(clamped, 4)))
            if isinstance(step, int):
                int_offset = int(round(clamped - float(minimum)))
                if int_offset % step != 0:
                    clamped = float(int(minimum) + (int_offset // step) * step)
        return float(clamped)

    int_min = int(round(float(minimum)))
    int_max = int(round(float(maximum)))
    int_val = int(round(clamped))
    if step is not None:
        int_step = int(round(float(step)))
        if int_step > 1:
            steps = round((int_val - int_min) / int_step)
            int_val = int_min + steps * int_step
            if int_val > int_max:
                int_val -= int_step
            if int_val < int_min:
                int_val = int_min
    return max(int_min, min(int_max, int_val))


def coerce_integer_value(value: Any) -> Any:
    if isinstance(value, bool):
        return int(value)
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return value


def align_to_property_type(target: Dict[str, Any], value: Any) -> Any:
    """Align resolved value to the underlying MIoT property type (bool, int, uint, float, string)."""
    prop_type = str(target.get("type") or "").lower()
    if prop_type == "bool":
        return coerce_boolean_value(value)
    if prop_type in {"int", "uint"} or prop_type.startswith("int") or prop_type.startswith("uint"):
        return coerce_integer_value(value)
    if prop_type == "float":
        try:
            return float(value)
        except (TypeError, ValueError):
            return value
    if prop_type == "string":
        return str(value).strip() if value is not None else ""
    return value


def coerce_value_for_target(capability_name: str, target: Dict[str, Any], value: Any) -> Any:
    if value is None:
        return value

    definition = CAPABILITY_REGISTRY.get(capability_name, {})
    resolved = value

    # 1. If target has an enum value_list, try resolving enum first and return the exact enum value
    if target.get("value_list"):
        enum_val, matched = coerce_enum_value(target, resolved, definition)
        if matched:
            return align_to_property_type(target, enum_val)

    # 2. If target has a numeric range, clamp and align to step
    if target.get("range"):
        resolved = coerce_range_value(target, resolved, definition)
        return align_to_property_type(target, resolved)

    # 3. Otherwise apply capability resolution strategies without overwriting target's native type
    for strategy in definition.get("value_resolution", []):
        if strategy == "boolean":
            resolved = coerce_boolean_value(resolved)
        elif strategy == "enum":
            enum_val, matched = coerce_enum_value(target, resolved, definition)
            if matched:
                return align_to_property_type(target, enum_val)
        elif strategy == "range":
            resolved = coerce_range_value(target, resolved, definition)
        elif strategy == "integer":
            resolved = coerce_integer_value(resolved)
        elif strategy == "string" and str(target.get("type") or "").lower() in {"", "string"}:
            resolved = str(resolved).strip()

    return align_to_property_type(target, resolved)


def coerce_raw_property_value(prop_or_target: Any, value: Any) -> Any:
    """Coerce a value for any raw MIoT property (DevProp or dict target) before calling device.set()."""
    if value is None:
        return value
    if isinstance(prop_or_target, dict):
        target = prop_or_target
    else:
        target = normalize_property(prop_or_target)

    if target.get("value_list"):
        # Merge semantic inputs from mode, fan_speed, and motor_control for rich Chinese/English enum matching
        merged_semantics: Dict[str, List[str]] = {}
        for cap_key in ("mode", "fan_speed", "motor_control"):
            cap_def = CAPABILITY_REGISTRY.get(cap_key, {})
            for sem_k, sem_v in cap_def.get("semantic_inputs", {}).items():
                merged_semantics.setdefault(sem_k, []).extend(sem_v)
        enum_val, matched = coerce_enum_value(target, value, {"semantic_inputs": merged_semantics})
        if matched:
            return align_to_property_type(target, enum_val)

    if target.get("range"):
        value = coerce_range_value(target, value)

    return align_to_property_type(target, value)


def build_standard_capability_definition(capability_name: str, target: Dict[str, Any]) -> Dict[str, Any]:
    definition = get_capability_definition(capability_name)
    value_schema: Dict[str, Any] = {"type": target.get("type") or definition["value_type"]}
    if target.get("range"):
        value_schema["range"] = target["range"]
    if target.get("unit"):
        value_schema["unit"] = target["unit"]
    if target.get("value_list"):
        value_schema["enum"] = target["value_list"]

    return {
        "name": capability_name,
        "label": definition["label"],
        "kind": target.get("kind"),
        "backing_name": target.get("name"),
        "description": target.get("description") or definition["description"],
        "readable": target.get("readable", False),
        "writable": target.get("writable", False),
        "value_resolution": definition.get("value_resolution", []),
        "value_schema": value_schema,
    }


def build_standard_capability_schema(capability_profile: Dict[str, Any]) -> Dict[str, Any]:
    controls = capability_profile.get("controls", {})
    schema: Dict[str, Any] = {
        "primary_domain": capability_profile.get("primary_domain", "generic"),
        "device_domains": capability_profile.get("device_domains", ["generic"]),
        "capability_families": capability_profile.get("capability_families", []),
        "capabilities": [],
        "preferred_tools": [],
    }

    for capability_name, definition in CAPABILITY_REGISTRY.items():
        if definition["kind"] != "property":
            continue
        target = controls.get(capability_name)
        if not target:
            continue
        schema["capabilities"].append(build_standard_capability_definition(capability_name, target))
        schema["preferred_tools"].append(to_client_tool_name(definition["preferred_tool"]))

    if controls.get("toggle"):
        definition = get_capability_definition("toggle")
        schema["capabilities"].append(
            {
                "name": "toggle",
                "label": definition["label"],
                "kind": "action",
                "backing_name": controls["toggle"].get("name"),
                "description": controls["toggle"].get("description") or definition["description"],
                "readable": False,
                "writable": True,
                "value_schema": {"type": "none"},
            }
        )
        schema["preferred_tools"].append(to_client_tool_name(definition["preferred_tool"]))

    schema["preferred_tools"] = list(dict.fromkeys(schema["preferred_tools"]))
    return schema


def describe_supported_operations(supported_operations: Dict[str, bool]) -> List[Dict[str, Any]]:
    descriptions: List[Dict[str, Any]] = []
    for operation_name, enabled in supported_operations.items():
        capability_name = OPERATION_CAPABILITY_MAP.get(operation_name)
        capability = get_capability_definition(capability_name) if capability_name else None
        if operation_name == "turn_on":
            preferred_tool = "turn_on_device"
            internal_tool = "turn_on_device"
        elif operation_name == "turn_off":
            preferred_tool = "turn_off_device"
            internal_tool = "turn_off_device"
        elif capability:
            preferred_tool = to_client_tool_name(capability["preferred_tool"])
            internal_tool = capability["preferred_tool"]
        elif operation_name in {"set_property", "run_action"}:
            preferred_tool = "control_device"
            internal_tool = "control_device"
        else:
            preferred_tool = "control_device"
            internal_tool = "control_device"
        descriptions.append(
            {
                "operation": operation_name,
                "enabled": enabled,
                "capability": capability_name,
                "preferred_tool": preferred_tool,
                "internal_tool": internal_tool,
            }
        )
    return descriptions


def summarize_capabilities(properties: List[Any], actions: List[Any]) -> Dict[str, Any]:
    property_names = [getattr(prop, "name", "") for prop in properties]
    action_names = [getattr(action, "name", "") for action in actions]

    support_summary: Dict[str, Any] = {
        "properties": [normalize_property(prop) for prop in properties],
        "actions": [normalize_action(action) for action in actions],
    }
    for capability_name, definition in CAPABILITY_REGISTRY.items():
        supported = False
        if definition["kind"] == "property":
            supported = find_supported_name(property_names, definition["aliases"]) is not None
        elif definition["kind"] == "action":
            supported = find_supported_name(action_names, definition["aliases"]) is not None
        support_summary[f"supports_{capability_name}"] = supported
    return support_summary
