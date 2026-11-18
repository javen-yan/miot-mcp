INTENT_DEFINITIONS = {
    "execute_scene": {
        "keywords": ["场景", "回家模式", "离家模式", "睡眠场景", "起床模式", "观影模式"],
        "kind": "scene",
        "strip_keywords": ["场景", "执行", "运行", "启动", "触发"],
    },
    "turn_on": {
        "keywords": ["打开", "开启", "开一下", "启动", "亮起", "拉开", "升起", "开灯", "开空调", "开风扇"],
        "kind": "operation",
    },
    "turn_off": {
        "keywords": ["关闭", "关掉", "关了", "关上", "熄灭", "合上", "拉上", "停止", "关灯", "关空调", "关风扇"],
        "kind": "operation",
    },
    "toggle": {
        "keywords": ["切换", "反转"],
        "kind": "operation",
    },
    "get_device": {
        "keywords": ["查看", "看看", "状态", "多少", "查询", "获取", "几度", "湿度"],
        "kind": "query",
    },
}
