STANDARD_CAPABILITIES = {
    "cover_position": {
        "kind": "property",
        "aliases": ["target-position", "target_position", "position"],
        "label": "Cover Position",
        "value_type": "integer",
        "value_resolution": ["range", "enum", "integer"],
        "intent_keywords": ["窗帘", "开合度", "开合", "位置"],
        "intent_strip_keywords": ["开合度", "开合", "位置", "%", "百分之"],
        "intent_requires_number": True,
        "intent_priority": 40,
        "preferred_tool": "set_cover_position",
        "families": ["cover_position"],
        "domains": ["cover"],
        "supported_device_types": ["curtain", "window-opener", "airer", "roller-shade"],
        "description": "Cover position capability (0-100%) with device-provided range metadata when available.",
    },
    "motor_control": {
        "kind": "property",
        "aliases": ["motor-control", "motor_control"],
        "label": "Motor Control",
        "value_type": "integer",
        "value_resolution": ["enum", "integer"],
        "semantic_inputs": {
            "open": ["open", "up", "打开", "开启", "拉开", "升起", "上升", "on", "true"],
            "close": ["close", "down", "关闭", "关掉", "关上", "合上", "拉上", "下降", "降下", "off", "false"],
            "pause": ["pause", "stop", "暂停", "停止", "停"],
        },
        "preferred_tool": "control_device",
        "families": ["cover_motor", "switchable"],
        "domains": ["cover"],
        "supported_device_types": ["curtain", "window-opener", "airer", "roller-shade"],
        "description": "Motor directional control (open/close/pause/up/down) for curtains, airers, and openers.",
    },
}

STANDARD_OPERATION_CAPABILITY_MAP = {
    "set_cover_position": "cover_position",
}
