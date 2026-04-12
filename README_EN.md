# Mijia MCP Server

[中文文档](README.md) | English

A productized Mijia MCP server built on top of `mijiaAPI 3.x`. Clients do not need to understand `did`, `siid/piid/aiid`, or other low-level protocol details up front. The server is designed around homes, rooms, device names, and scene names first.

## What This Version Solves

- For AI clients: exposes stable product-level tools instead of raw protocol fields
- For real smart-home workflows: browse homes and rooms first, then resolve devices, then control them
- For MCP compatibility: tools return structured results, and service/login state is directly consumable
- For future growth: standard capability schemas, profile-driven controls, and resource models can keep evolving

## Current Capabilities

### Service and Login
- `get_service_status`
- `prepare_login`
- `reconnect_service`
- `clear_saved_login`
- `refresh_devices`
- `get_tool_catalog`
- `ping`

### Homes and Devices
- `get_home_overview`
- `list_homes`
- `list_devices`
- `get_device`
- `get_device_status`
- `get_device_capabilities`

### Device Control
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

### Scenes and Consumables
- `list_scenes`
- `execute_scene`
- `get_consumable_items`

### MCP Resources
- `mijia://service`
- `mijia://homes`
- `mijia://devices`
- `mijia://scenes`
- `mijia://capabilities`
- `mijia://tooling`

## Installation

Python `3.10+` is recommended.

```bash
poetry install
```

If you do not use Poetry:

```bash
pip install -r requirements.txt
```

## Start the Server

```bash
poetry run python mcp_server/mcp_server.py
```

Test the MCP handshake:

```bash
poetry run python mcp_server/mcp_test.py
```

## Authentication

`mijiaAPI 3.x` removed username/password login. QR login is the only supported path.

When login is needed, the server will:

- generate a browser-friendly page at `~/.miot-mcp/qr.html`
- also generate a QR image at `~/.miot-mcp/qr.png`
- open `qr.html` in the default browser by default
- only fall back to the image viewer or terminal QR when browser open is unavailable

Credentials are stored in:

```text
~/.miot-mcp/auth_data.json
```

### Recommended Login Flow

1. Call `prepare_login`
2. Call `get_service_status`
3. Read `service.qr.page_path` or `service.qr.image_path`
4. After scanning, call `reconnect_service` or go straight to `refresh_devices`

### Login State Fields

Both `get_service_status` and `mijia://service` return structured login state. The most useful fields are:

- `service.connected`
- `service.has_saved_login`
- `service.qr.open_mode`
- `service.qr.page_path`
- `service.qr.image_path`
- `service.qr.login_url`
- `assistant_summary`
- `next_steps.should_scan_qr`

## Environment Variables

```bash
export MIJIA_ENABLE_QR="true"
export MIJIA_QR_OPEN_MODE="browser"
export MIJIA_LOG_LEVEL="INFO"
```

Notes:

- `MIJIA_ENABLE_QR`: whether QR login is enabled, defaults to `true`
- `MIJIA_QR_OPEN_MODE`: advanced override for QR opening, supports `browser`, `viewer`, or `none`
- `MIJIA_LOG_LEVEL`: one of `DEBUG`, `INFO`, `WARNING`, `ERROR`

## MCP Client Configuration Example

Using the virtualenv Python directly is recommended over `poetry run`.

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

## Recommended Tool Flow

For most AI clients, the recommended path is:

1. `prepare_login`
2. `get_service_status`
3. `refresh_devices`
4. `get_home_overview`
5. `get_device_status`
6. `control_by_intent`
7. `list_scenes`
8. `execute_scene`

If the client needs more explicit and stable routing, add:

1. `list_homes`
2. `list_devices`
3. `get_device`
4. `get_device_capabilities`
5. `control_device`

## Common Tools

### `prepare_login`

Prepares QR login proactively. By default it reuses existing QR artifacts when possible. If you need a fresh QR login flow, pass `force_reauth=true`.

### `get_service_status`

Returns service connection state, auth file path, log path, QR paths, and next-step hints.

### `get_home_overview`

Returns a room-first overview of homes and devices. This is usually the best way for a client to understand the household layout.

### `get_device_status`

Returns the current state of a device, supported operations, and recommended next actions.

### `get_device_capabilities`

Returns the standard capability schema and profile-driven controls for stable client routing.

### `control_by_intent`

Natural-language-like control entry point. Best for most everyday interactions, such as "set the bedroom lamp brightness to 30%".

### `control_device`

Structured control entry point. Best when the client already knows the target operation and arguments.

## Examples

### Get Service Status

```json
{
  "name": "get_service_status",
  "arguments": {}
}
```

### Prepare Login

```json
{
  "name": "prepare_login",
  "arguments": {
    "reopen_qr": true
  }
}
```

### Refresh Device and Room Mapping

```json
{
  "name": "refresh_devices",
  "arguments": {}
}
```

### Get Home Overview

```json
{
  "name": "get_home_overview",
  "arguments": {}
}
```

### Get Device Status

```json
{
  "name": "get_device_status",
  "arguments": {
    "device_name": "Ceiling Light",
    "room": "Living Room"
  }
}
```

### Get Capability Schema

```json
{
  "name": "get_device_capabilities",
  "arguments": {
    "device_name": "Desk Lamp",
    "room": "Bedroom"
  }
}
```

### Natural Language Control

```json
{
  "name": "control_by_intent",
  "arguments": {
    "query": "Set the bedroom lamp brightness to 30%"
  }
}
```

### Structured Control

```json
{
  "name": "control_device",
  "arguments": {
    "operation": "set_color_temperature",
    "device_name": "Desk Lamp",
    "room": "Bedroom",
    "value": 4000
  }
}
```

### Execute a Scene

```json
{
  "name": "execute_scene",
  "arguments": {
    "scene_name": "Coming Home"
  }
}
```

## Current Scope

This version focuses on the most common home-control workflows:

- browsing homes and rooms
- resolving devices
- controlling common standard capabilities
- exposing standardized capability schemas
- executing scenes
- reading consumable items

The most important capability families currently covered are:

- power
- brightness
- color temperature
- target temperature
- mode
- fan speed
- cover position

Lower-level or more device-specific controls can still be extended through `control_device`, but they are no longer the default public usage model.

## Code Structure

The server currently has three main layers:

- `adapter/`
  Talks to `mijiaAPI`, handles login, device discovery, and QR login UX
- `mcp_server/core/`
  Handles result formatting, capability processing, intent routing, and normalization
- `mcp_server/device_definitions/` and `mcp_server/device_resources/`
  Define standard capabilities, intents, and product-style resource models

Capabilities and routing are now driven by explicit definition tables instead of plugin-style auto discovery. This makes the behavior clearer and more stable for AI clients.
