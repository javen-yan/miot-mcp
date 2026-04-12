"""Capability profile and value resolution engine."""

from typing import Any, Dict, List

from mcp_server.core.normalizers import (
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
    domains: List[str] = []
    for capability_name, definition in CAPABILITY_REGISTRY.items():
        capability_domains = definition.get("domains", [])
        if not capability_domains:
            continue
        if not capability_matches_device(definition, device):
            continue
        matched = False
        if definition["kind"] == "property":
            matched = find_supported_property(properties, definition["aliases"]) is not None
        elif definition["kind"] == "action":
            matched = find_supported_action(actions, definition["aliases"]) is not None
        if matched:
            for domain in capability_domains:
                if domain not in domains:
                    domains.append(domain)
    return domains or ["generic"]


def get_capability_target(prop: Any, target_kind: str) -> Dict[str, Any]:
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
    }


def get_action_target(action: Any, target_kind: str) -> Dict[str, Any]:
    return {
        "kind": "action",
        "capability": target_kind,
        "name": getattr(action, "name", None),
        "description": getattr(action, "desc", None),
    }


def build_device_capability_profile(device: Dict[str, Any], properties: List[Any], actions: List[Any]) -> Dict[str, Any]:
    controls: Dict[str, Dict[str, Any]] = {}
    for capability_name, definition in CAPABILITY_REGISTRY.items():
        if not capability_matches_device(definition, device):
            continue
        if definition["kind"] == "property":
            prop = find_supported_property(properties, definition["aliases"], writable_only=True)
            if prop:
                controls[capability_name] = get_capability_target(prop, capability_name)
        elif definition["kind"] == "action":
            action = find_supported_action(actions, definition["aliases"])
            if action:
                controls[capability_name] = get_action_target(action, capability_name)

    device_domains = infer_device_domains(device, properties, actions)
    supported_operations = {}
    for operation_name, capability_name in OPERATION_CAPABILITY_MAP.items():
        if operation_name == "toggle":
            supported_operations[operation_name] = "toggle" in controls or "power" in controls
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
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "on", "open", "yes"}:
            return True
        if normalized in {"false", "0", "off", "close", "no"}:
            return False
    return value


def coerce_enum_value(target: Dict[str, Any], value: Any, definition: Dict[str, Any]) -> Any:
    value_list = target.get("value_list") or []
    if not value_list:
        return value

    semantic_inputs = definition.get("semantic_inputs", {})
    normalized_input = str(value).strip().lower()
    semantic_alias = None
    for semantic_key, aliases in semantic_inputs.items():
        if normalized_input in [str(alias).strip().lower() for alias in aliases]:
            semantic_alias = semantic_key
            break

    for item in value_list:
        candidates = [
            str(item.get("value", "")).strip().lower(),
            str(item.get("description", "")).strip().lower(),
            str(item.get("desc", "")).strip().lower(),
            str(item.get("desc_zh_cn", "")).strip().lower(),
            str(item.get("desc_en", "")).strip().lower(),
            str(item.get("name", "")).strip().lower(),
        ]
        if semantic_alias and semantic_alias.lower() in [candidate for candidate in candidates if candidate]:
            return item.get("value")
        if normalized_input and normalized_input in [candidate for candidate in candidates if candidate]:
            return item.get("value")
    return value


def coerce_range_value(target: Dict[str, Any], value: Any) -> Any:
    value_range = target.get("range")
    if not (isinstance(value_range, list) and len(value_range) >= 2):
        return value
    try:
        numeric_value = int(value)
    except (TypeError, ValueError):
        return value
    minimum = int(value_range[0])
    maximum = int(value_range[1])
    return max(minimum, min(maximum, numeric_value))


def coerce_integer_value(value: Any) -> Any:
    try:
        return int(value)
    except (TypeError, ValueError):
        return value


def coerce_value_for_target(capability_name: str, target: Dict[str, Any], value: Any) -> Any:
    if value is None:
        return value

    definition = get_capability_definition(capability_name)
    resolved = value
    for strategy in definition.get("value_resolution", []):
        if strategy == "boolean":
            resolved = coerce_boolean_value(resolved)
        elif strategy == "enum":
            resolved = coerce_enum_value(target, resolved, definition)
        elif strategy == "range":
            resolved = coerce_range_value(target, resolved)
        elif strategy == "integer":
            resolved = coerce_integer_value(resolved)
        elif strategy == "string":
            resolved = str(resolved).strip()
    return resolved


def build_standard_capability_definition(capability_name: str, target: Dict[str, Any]) -> Dict[str, Any]:
    definition = get_capability_definition(capability_name)
    value_schema: Dict[str, Any] = {"type": definition["value_type"]}
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
