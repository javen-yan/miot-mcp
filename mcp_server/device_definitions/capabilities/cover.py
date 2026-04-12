STANDARD_CAPABILITIES = {
    "cover_position": {
        "kind": "property",
        "aliases": ["motor-control", "target-position", "target_position", "position"],
        "label": "Cover Position",
        "value_type": "integer",
        "value_resolution": ["range", "enum", "integer"],
        "intent_keywords": ["窗帘", "开合", "位置"],
        "intent_strip_keywords": ["窗帘", "开合", "位置"],
        "intent_priority": 40,
        "preferred_tool": "set_cover_position",
        "families": ["cover_position"],
        "domains": ["cover"],
        "supported_device_types": ["curtain", "window-opener", "airer"],
        "description": "Cover position capability with device-provided range metadata when available.",
    },
}

STANDARD_OPERATION_CAPABILITY_MAP = {
    "set_cover_position": "cover_position",
}
