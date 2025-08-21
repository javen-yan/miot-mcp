# Mijia Smart Device MCP Server

[中文文档](README_ZH.md) | English

A Mijia smart device control server based on Model Context Protocol (MCP), providing device discovery, property read/write, action invocation, status monitoring and other functions.

## Features

### 🔌 Connection Management
- Support username/password login
- Support QR code login
- Automatic save and load authentication information
- Connection status monitoring

### 📱 Device Management
- Automatic Mijia device discovery
- Device search and filtering
- Get device properties and action lists
- Batch operation support

### 📊 Status Monitoring
- Real-time device status acquisition
- Device status caching
- Batch status refresh
- Status change tracking

### 🛠️ System Functions
- Resource cache management
- Detailed error handling and logging
- Server status monitoring
- Connectivity testing

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Authentication

Set environment variables:

```bash
export MIJIA_USERNAME="your_username"
export MIJIA_PASSWORD="your_password"
export MIJIA_ENABLE_QR="false"
export MIJIA_LOG_LEVEL="INFO"
```

### 3. Start Server

```bash
python mcp_server/mcp_server.py
```

### 4. Test Connection

```bash
python mcp_test.py
```

## AI Tool Integration

### Claude Desktop Integration

Add the following configuration to your Claude Desktop config file:

**macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
**Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "mijia": {
      "command": "python",
      "args": ["/path/to/miot-agent/mcp_server/mcp_server.py"],
      "env": {
        "MIJIA_USERNAME": "your_username",
        "MIJIA_PASSWORD": "your_password",
        "MIJIA_ENABLE_QR": "false",
        "MIJIA_LOG_LEVEL": "INFO"
      }
    }
  }
}
```

### Continue.dev Integration

Add to your Continue configuration:

```json
{
  "mcpServers": {
    "mijia": {
      "command": "python",
      "args": ["/path/to/miot-agent/mcp_server/mcp_server.py"],
      "env": {
        "MIJIA_USERNAME": "your_username",
        "MIJIA_PASSWORD": "your_password",
        "MIJIA_ENABLE_QR": "false",
        "MIJIA_LOG_LEVEL": "INFO"
      }
    }
  }
}
```

### Cline Integration

For Cline (formerly Claude Dev), add the MCP server configuration:

```json
{
  "mcp": {
    "servers": {
      "mijia": {
        "command": "python",
        "args": ["/path/to/miot-agent/mcp_server/mcp_server.py"],
        "env": {
          "MIJIA_USERNAME": "your_username",
          "MIJIA_PASSWORD": "your_password",
          "MIJIA_ENABLE_QR": "false",
          "MIJIA_LOG_LEVEL": "INFO"
        }
      }
    }
  }
}
```

### Generic MCP Client Integration

For any MCP-compatible client:

1. **Command**: `python /path/to/miot-agent/mcp_server/mcp_server.py`
2. **Environment Variables**:
   - `MIJIA_USERNAME`: Your Mijia account username
   - `MIJIA_PASSWORD`: Your Mijia account password
   - `MIJIA_ENABLE_QR`: Set to "true" for QR code login (optional)
   - `MIJIA_LOG_LEVEL`: Log level (DEBUG, INFO, WARNING, ERROR)

### Verification

After integration, you should see the following tools available in your AI assistant:

- **Connection**: `connect`, `connect_with_qr`, `disconnect`, `ping`
- **Device Management**: `discover_devices`, `search_devices`
- **Property Operations**: `get_property_value`, `set_property_value`, `batch_set_properties`
- **Action Operations**: `call_action`
- **Status Monitoring**: `get_device_status`, `refresh_all_device_status`
- **System Management**: `get_server_status`, `clear_cache`

And these resources:
- `mijia://devices` - Device list
- `mijia://config` - Configuration information
- `mijia://device/{device_id}/properties` - Device properties
- `mijia://device/{device_id}/actions` - Device actions

## Tool Usage Guide

### Connection Management

#### Connect to Mijia Cloud Service
```json
{
  "method": "tools/call",
  "params": {
    "name": "connect",
    "arguments": {}
  }
}
```

#### Disconnect
```json
{
  "method": "tools/call",
  "params": {
    "name": "disconnect",
    "arguments": {}
  }
}
```

### Device Discovery and Management

#### Discover Devices
```json
{
  "method": "tools/call",
  "params": {
    "name": "discover_devices",
    "arguments": {}
  }
}
```

#### Search Devices
```json
{
  "method": "tools/call",
  "params": {
    "name": "search_devices",
    "arguments": {
      "name_filter": "desk_lamp",
      "model_filter": "xiaomi",
      "online_only": true
    }
  }
}
```

### Device Property Operations

#### Get Device Property List
```json
{
  "method": "tools/call",
  "params": {
    "name": "get_device_properties",
    "arguments": {
      "device_id": "123456789"
    }
  }
}
```

#### Get Property Value
```json
{
  "method": "tools/call",
  "params": {
    "name": "get_property_value",
    "arguments": {
      "device_id": "123456789",
      "siid": 2,
      "piid": 1
    }
  }
}
```

#### Set Property Value
```json
{
  "method": "tools/call",
  "params": {
    "name": "set_property_value",
    "arguments": {
      "device_id": "123456789",
      "siid": 2,
      "piid": 1,
      "value": true
    }
  }
}
```

#### Batch Set Properties
```json
{
  "method": "tools/call",
  "params": {
    "name": "batch_set_properties",
    "arguments": {
      "operations": [
        {
          "device_id": "123456789",
          "siid": 2,
          "piid": 1,
          "value": true
        },
        {
          "device_id": "987654321",
          "siid": 3,
          "piid": 2,
          "value": 50
        }
      ]
    }
  }
}
```

### Device Action Invocation

#### Get Device Action List
```json
{
  "method": "tools/call",
  "params": {
    "name": "get_device_actions",
    "arguments": {
      "device_id": "123456789"
    }
  }
}
```

#### Call Device Action
```json
{
  "method": "tools/call",
  "params": {
    "name": "call_action",
    "arguments": {
      "device_id": "123456789",
      "siid": 2,
      "aiid": 1,
      "params": []
    }
  }
}
```

### Status Monitoring

#### Get Device Status
```json
{
  "method": "tools/call",
  "params": {
    "name": "get_device_status",
    "arguments": {
      "device_id": "123456789"
    }
  }
}
```

#### Refresh All Device Status
```json
{
  "method": "tools/call",
  "params": {
    "name": "refresh_all_device_status",
    "arguments": {}
  }
}
```

#### Get Cached Status
```json
{
  "method": "tools/call",
  "params": {
    "name": "get_cached_device_status",
    "arguments": {
      "device_id": "123456789"
    }
  }
}
```

### System Management

#### Get Server Status
```json
{
  "method": "tools/call",
  "params": {
    "name": "get_server_status",
    "arguments": {}
  }
}
```

#### Clear Cache
```json
{
  "method": "tools/call",
  "params": {
    "name": "clear_cache",
    "arguments": {}
  }
}
```

#### Test Connectivity
```json
{
  "method": "tools/call",
  "params": {
    "name": "ping",
    "arguments": {
      "message": "hello"
    }
  }
}
```

## Resource Access

### Get Device List
```json
{
  "method": "resources/read",
  "params": {
    "uri": "mijia://devices"
  }
}
```

### Get Configuration Information
```json
{
  "method": "resources/read",
  "params": {
    "uri": "mijia://config"
  }
}
```

### Get Device Properties
```json
{
  "method": "resources/read",
  "params": {
    "uri": "mijia://device/123456789/properties"
  }
}
```

### Get Device Actions
```json
{
  "method": "resources/read",
  "params": {
    "uri": "mijia://device/123456789/actions"
  }
}
```

## Error Handling

All tool calls return a unified error format:

```json
{
  "success": false,
  "error": "Error description",
  "error_code": "ERROR_CODE",
  "timestamp": "2024-01-01T12:00:00Z"
}
```

Common error codes:
- `ADAPTER_NOT_INITIALIZED`: Adapter not initialized
- `DEVICE_NOT_FOUND`: Device not found
- `PROPERTY_NOT_FOUND`: Property not found
- `ACTION_NOT_FOUND`: Action not found
- `CONNECTION_FAILED`: Connection failed
- `AUTHENTICATION_FAILED`: Authentication failed

## Log Configuration

Log level can be set through environment variables:

```bash
# Environment variable
export MIJIA_LOG_LEVEL="DEBUG"
```

## Project Structure

```
miot-agent/
├── adapter/
│   ├── mijia_adapter.py      # Mijia adapter implementation
│   └── mijia_config.py       # Configuration management
├── mcp_server/
│   ├── mcp_server.py         # MCP server main program
│   └── server_config.json    # Server configuration
├── requirements.txt          # Project dependencies
├── mcp_test.py              # Test script
└── README.md                # Project documentation
```

## Development Guide

### Adding New Tools

1. Add tool function in `mcp_server.py`:

```python
@mcp.tool()
async def your_new_tool(param1: str, param2: int = 0) -> str:
    """Tool description
    
    Args:
        param1: Parameter 1 description
        param2: Parameter 2 description
    
    Returns:
        Return value description
    """
    # Implementation logic
    pass
```

2. Add tool configuration in `server_config.json`:

```json
{
  "name": "your_new_tool",
  "description": "Tool description",
  "category": "category_name"
}
```

### Adding New Resources

1. Add resource handler function in `mcp_server.py`:

```python
@mcp.resource("mijia://your-resource")
async def get_your_resource() -> str:
    """Resource description"""
    # Implementation logic
    pass
```

2. Add resource configuration in `server_config.json`:

```json
{
  "uri": "mijia://your-resource",
  "name": "Resource name",
  "description": "Resource description",
  "mimeType": "application/json"
}
```

## License

MIT License

## Contributing

Welcome to submit Issues and Pull Requests!