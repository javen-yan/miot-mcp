"""Standard capability definitions used by BaseDevice resources and control routing."""

from typing import Any, Dict

from mcp_server.device_definitions.capabilities.climate import (
    STANDARD_CAPABILITIES as CLIMATE_CAPABILITIES,
    STANDARD_OPERATION_CAPABILITY_MAP as CLIMATE_OPERATION_MAP,
)
from mcp_server.device_definitions.capabilities.cover import (
    STANDARD_CAPABILITIES as COVER_CAPABILITIES,
    STANDARD_OPERATION_CAPABILITY_MAP as COVER_OPERATION_MAP,
)
from mcp_server.device_definitions.capabilities.lighting import (
    STANDARD_CAPABILITIES as LIGHTING_CAPABILITIES,
    STANDARD_OPERATION_CAPABILITY_MAP as LIGHTING_OPERATION_MAP,
)
from mcp_server.device_definitions.capabilities.power import (
    STANDARD_CAPABILITIES as POWER_CAPABILITIES,
    STANDARD_OPERATION_CAPABILITY_MAP as POWER_OPERATION_MAP,
)


CAPABILITY_REGISTRY: Dict[str, Dict[str, Any]] = {
    **LIGHTING_CAPABILITIES,
    **CLIMATE_CAPABILITIES,
    **COVER_CAPABILITIES,
    **POWER_CAPABILITIES,
}

OPERATION_CAPABILITY_MAP: Dict[str, str] = {
    **POWER_OPERATION_MAP,
    **LIGHTING_OPERATION_MAP,
    **CLIMATE_OPERATION_MAP,
    **COVER_OPERATION_MAP,
}


for capability_name, definition in CAPABILITY_REGISTRY.items():
    definition.setdefault("source_module", f"mcp_server.device_definitions.standard_capabilities:{capability_name}")


def get_capability_definition(capability_name: str) -> Dict[str, Any]:
    return CAPABILITY_REGISTRY[capability_name]


def to_client_tool_name(tool_name: str) -> str:
    return tool_name


def get_capability_catalog() -> Dict[str, Any]:
    catalog: Dict[str, Any] = {}
    for capability_name, definition in CAPABILITY_REGISTRY.items():
        catalog[capability_name] = {
            "kind": definition["kind"],
            "aliases": definition["aliases"],
            "domains": definition["domains"],
            "families": definition["families"],
            "value_type": definition["value_type"],
            "value_resolution": definition.get("value_resolution", []),
            "intent_keywords": definition.get("intent_keywords", []),
            "intent_priority": definition.get("intent_priority"),
            "preferred_tool": to_client_tool_name(definition["preferred_tool"]),
            "internal_tool": definition["preferred_tool"],
            "description": definition["description"],
            "source_module": definition.get("source_module"),
        }
    return catalog
