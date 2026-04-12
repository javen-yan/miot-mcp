INTENT_DEFINITIONS = {
    "execute_scene": {
        "keywords": ["场景", "回家", "离家", "睡眠"],
        "kind": "scene",
        "strip_keywords": ["场景"],
    },
    "turn_on": {
        "keywords": ["打开", "开启"],
        "kind": "operation",
    },
    "turn_off": {
        "keywords": ["关闭", "关掉"],
        "kind": "operation",
    },
    "toggle": {
        "keywords": ["切换"],
        "kind": "operation",
    },
    "get_device": {
        "keywords": ["查看", "看看", "状态", "多少", "查询", "获取"],
        "kind": "query",
    },
}
