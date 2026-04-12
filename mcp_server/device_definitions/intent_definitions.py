"""Intent definitions for natural-language routing."""

from typing import Any, Dict

from mcp_server.device_definitions.intents.core import INTENT_DEFINITIONS


INTENT_REGISTRY: Dict[str, Dict[str, Any]] = {
    name: {
        **definition,
        "source_module": f"mcp_server.device_definitions.intent_definitions:{name}",
    }
    for name, definition in INTENT_DEFINITIONS.items()
}


def get_intent_catalog() -> Dict[str, Dict[str, Any]]:
    return {
        intent_name: {
            "kind": intent_definition.get("kind"),
            "keywords": intent_definition.get("keywords", []),
            "source_module": intent_definition.get("source_module"),
        }
        for intent_name, intent_definition in INTENT_REGISTRY.items()
    }
