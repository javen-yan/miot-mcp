STANDARD_CAPABILITIES = {
    "power": {
        "kind": "property",
        "aliases": ["on", "switch-status", "power", "status"],
        "label": "Power",
        "value_type": "boolean",
        "value_resolution": ["boolean"],
        "preferred_tool": "turn_on_device",
        "families": ["switchable"],
        "domains": ["switch"],
        "description": "Writable power capability backed by a device property.",
    },
    "toggle": {
        "kind": "action",
        "aliases": ["toggle"],
        "label": "Toggle",
        "value_type": "none",
        "preferred_tool": "control_device",
        "families": ["toggleable"],
        "domains": ["switch"],
        "description": "Toggle capability backed by an action or a power property.",
    },
}

STANDARD_OPERATION_CAPABILITY_MAP = {
    "turn_on": "power",
    "turn_off": "power",
    "toggle": "toggle",
}
