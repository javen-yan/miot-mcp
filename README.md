# 米家 MCP Server

中文文档 | [English](README_EN.md)

一个基于 `mijiaAPI 3.x` 的产品化米家 MCP 服务。它不再要求客户端先理解 `did`、`siid/piid/aiid` 这些协议细节，而是优先面向“家庭、房间、设备名、场景名”提供更自然的查询和控制能力。

## 这版解决什么问题

- 面向 AI 客户端：优先暴露稳定、清晰的产品级工具，而不是底层协议字段
- 面向真实家庭场景：先看家庭与房间，再定位设备，再执行控制
- 面向 MCP 标准：工具返回结构化结果，服务状态和登录状态可直接被客户端消费
- 面向扩展：标准能力 schema、profile 驱动控制、资源模型可以继续演进

## 当前能力

### 服务与登录
- `get_service_status`
- `prepare_login`
- `reconnect_service`
- `clear_saved_login`
- `refresh_devices`
- `get_tool_catalog`
- `ping`

### 家庭与设备
- `get_home_overview`
- `list_homes`
- `list_devices`
- `get_device`
- `get_device_status`
- `get_device_capabilities`

### 设备控制
- `control_by_intent`
- `control_device`
- `turn_on_device`
- `turn_off_device`
- `set_brightness`
- `set_color_temperature`
- `set_target_temperature`
- `set_hvac_mode`
- `set_fan_speed`
- `set_cover_position`

### 场景与耗材
- `list_scenes`
- `execute_scene`
- `get_consumable_items`

### MCP 资源
- `mijia://service`
- `mijia://homes`
- `mijia://devices`
- `mijia://scenes`
- `mijia://capabilities`
- `mijia://tooling`

## 安装

建议使用 Python `3.10+`。

```bash
poetry install
```

如果你不用 Poetry：

```bash
pip install -r requirements.txt
```

## 启动

```bash
poetry run python mcp_server/mcp_server.py
```

测试握手：

```bash
poetry run python mcp_server/mcp_test.py
```

## 登录方式

`mijiaAPI 3.x` 已移除账号密码登录，只支持二维码登录。

首次需要登录时，服务会：

- 生成浏览器页：`~/.miot-mcp/qr.html`
- 同时生成二维码图片：`~/.miot-mcp/qr.png`
- 默认优先用系统浏览器打开 `qr.html`
- 只有浏览器打不开时，才回退到图片查看器或终端二维码

认证信息会保存到：

```text
~/.miot-mcp/auth_data.json
```

### 推荐登录主路径

1. 调用 `prepare_login`
2. 调用 `get_service_status`
3. 读取 `service.qr.page_path` 或 `service.qr.image_path`
4. 完成扫码后调用 `reconnect_service` 或直接 `refresh_devices`

### 登录相关状态

`get_service_status` 和 `mijia://service` 都会返回结构化登录状态，重点字段包括：

- `service.connected`
- `service.has_saved_login`
- `service.qr.open_mode`
- `service.qr.page_path`
- `service.qr.image_path`
- `service.qr.login_url`
- `assistant_summary`
- `next_steps.should_scan_qr`

## 环境变量

```bash
export MIJIA_ENABLE_QR="true"
export MIJIA_QR_OPEN_MODE="browser"
export MIJIA_LOG_LEVEL="INFO"
```

说明：

- `MIJIA_ENABLE_QR`：是否启用二维码登录，默认 `true`
- `MIJIA_QR_OPEN_MODE`：高级配置，支持 `browser` / `viewer` / `none`，默认 `browser`
- `MIJIA_LOG_LEVEL`：日志级别，支持 `DEBUG` / `INFO` / `WARNING` / `ERROR`

## MCP 客户端配置示例

推荐直接使用虚拟环境里的 Python，而不是 `poetry run`。

```json
{
  "mcpServers": {
    "mijia": {
      "command": "/path/to/venv/bin/python",
      "args": [
        "/path/to/miot-mcp/mcp_server/mcp_server.py"
      ],
      "env": {
        "MIJIA_ENABLE_QR": "true",
        "MIJIA_QR_OPEN_MODE": "browser",
        "MIJIA_LOG_LEVEL": "INFO"
      }
    }
  }
}
```

## 推荐调用路径

对于大多数 AI 客户端，建议优先这样使用：

1. `prepare_login`
2. `get_service_status`
3. `refresh_devices`
4. `get_home_overview`
5. `get_device_status`
6. `control_by_intent`
7. `list_scenes`
8. `execute_scene`

如果客户端需要更稳定、更显式的路由，再补充：

1. `list_homes`
2. `list_devices`
3. `get_device`
4. `get_device_capabilities`
5. `control_device`

## 常用工具说明

### `prepare_login`

主动准备二维码登录。默认优先复用已有二维码页；如果需要重新走一轮扫码，可以传 `force_reauth=true`。

### `get_service_status`

返回服务连接状态、认证文件路径、日志路径、二维码页路径、下一步建议。

### `get_home_overview`

按家庭和房间输出设备总览，适合客户端先理解家庭结构。

### `get_device_status`

查看单个设备当前状态、可用操作和推荐下一步。

### `get_device_capabilities`

返回标准能力 schema 和 profile 驱动控制项，适合需要稳定路由的客户端。

### `control_by_intent`

自然语言式控制入口。适合大多数日常使用场景，例如“把卧室台灯亮度调到 30%”。

### `control_device`

统一结构化控制入口。适合客户端已经知道目标操作和参数时使用。

## 使用示例

### 查看服务状态

```json
{
  "name": "get_service_status",
  "arguments": {}
}
```

### 主动准备登录

```json
{
  "name": "prepare_login",
  "arguments": {
    "reopen_qr": true
  }
}
```

### 刷新设备与房间映射

```json
{
  "name": "refresh_devices",
  "arguments": {}
}
```

### 查看家庭总览

```json
{
  "name": "get_home_overview",
  "arguments": {}
}
```

### 查看单个设备状态

```json
{
  "name": "get_device_status",
  "arguments": {
    "device_name": "吸顶灯",
    "room": "客厅"
  }
}
```

### 查看能力 schema

```json
{
  "name": "get_device_capabilities",
  "arguments": {
    "device_name": "台灯",
    "room": "卧室"
  }
}
```

### 自然语言控制

```json
{
  "name": "control_by_intent",
  "arguments": {
    "query": "把卧室台灯亮度调到30%"
  }
}
```

### 结构化控制

```json
{
  "name": "control_device",
  "arguments": {
    "operation": "set_color_temperature",
    "device_name": "台灯",
    "room": "卧室",
    "value": 4000
  }
}
```

### 执行场景

```json
{
  "name": "execute_scene",
  "arguments": {
    "scene_name": "回家模式"
  }
}
```

## 当前边界

这版 MCP 重点覆盖的是最常见的家庭控制路径：

- 家庭与房间浏览
- 设备定位
- 通用能力控制
- 标准化能力 schema 暴露
- 场景执行
- 耗材查询

已重点覆盖的典型能力包括：

- 开关
- 亮度
- 色温
- 目标温度
- 模式
- 风速
- 开合位置

更底层、更强定制的能力仍然可以继续往 `control_device` 扩展，但不再作为默认使用方式对外暴露。

## 代码结构

当前服务内部主要有三层：

- `adapter/`
  负责与 `mijiaAPI` 交互、登录、设备发现和二维码登录体验
- `mcp_server/core/`
  负责结果封装、能力计算、意图路由、标准化
- `mcp_server/device_definitions/` 与 `mcp_server/device_resources/`
  负责标准能力定义、意图定义和产品化资源模型

当前能力和路由不依赖插件自动发现，而是显式导入定义表。这样更清晰，也更适合 AI 客户端稳定调用。
