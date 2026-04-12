STANDARD_CAPABILITIES = {
    "brightness": {
        "kind": "property",
        "aliases": ["brightness"],
        "label": "Brightness",
        "value_type": "integer",
        "value_resolution": ["range", "enum", "integer"],
        "intent_keywords": ["亮度", "%", "调亮", "调暗"],
        "intent_strip_keywords": ["亮度"],
        "intent_default_value": 50,
        "intent_priority": 10,
        "preferred_tool": "set_brightness",
        "families": ["dimmable"],
        "domains": ["lighting"],
        "supported_device_types": ["light", "ceiling-light", "ambient-light", "night-light", "bathroom-light", "light-strip"],
        "description": "Brightness capability with device-provided range metadata when available.",
    },
    "color_temperature": {
        "kind": "property",
        "aliases": ["color-temperature", "color_temperature"],
        "label": "Color Temperature",
        "value_type": "integer",
        "value_resolution": ["enum", "range", "integer"],
        "semantic_inputs": {
            "暖": ["暖", "warm"],
            "冷": ["冷", "cool"],
        },
        "intent_keywords": ["色温", "冷光", "暖光"],
        "intent_strip_keywords": ["色温", "暖光", "冷光"],
        "intent_priority": 20,
        "preferred_tool": "set_color_temperature",
        "families": ["color_temperature"],
        "domains": ["lighting"],
        "supported_device_types": ["light", "ceiling-light", "ambient-light", "night-light", "bathroom-light", "light-strip"],
        "description": "Color temperature capability with device-provided range metadata when available.",
    },
}

STANDARD_OPERATION_CAPABILITY_MAP = {
    "set_brightness": "brightness",
    "set_color_temperature": "color_temperature",
}
