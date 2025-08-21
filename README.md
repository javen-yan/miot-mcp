# 米家智能设备 MCP 服务器

中文文档 | [English](README_EN.md)

基于 Model Context Protocol (MCP) 的米家智能设备控制服务器，提供设备发现、属性读写、动作调用、状态监控等功能。

## 功能特性

### 🔌 连接管理
- 支持用户名密码登录
- 支持二维码登录
- 自动保存和加载认证信息
- 连接状态监控

### 📱 设备管理
- 自动发现米家设备
- 设备搜索和过滤
- 获取设备属性和动作列表
- 批量操作支持

### 📊 状态监控
- 实时设备状态获取
- 设备状态缓存
- 批量状态刷新
- 状态变化追踪

### 🛠️ 系统功能
- 资源缓存管理
- 详细错误处理和日志
- 服务器状态监控
- 连通性测试

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置认证信息

设置环境变量：

```bash
export MIJIA_USERNAME="your_username"
export MIJIA_PASSWORD="your_password"
export MIJIA_ENABLE_QR="false"
export MIJIA_LOG_LEVEL="INFO"
```

### 3. 启动服务器

```bash
python mcp_server/mcp_server.py
```

### 4. 测试连接

```bash
python mcp_test.py
```

## AI 工具集成

### Claude Desktop 集成

在 Claude Desktop 配置文件中添加以下配置：

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

### Continue.dev 集成

在 Continue 配置中添加：

```json
{
  "mcpServers": {
    "mijia": {
      "command": "python",
      "args": ["/path/to/miot-agent/mcp_server/mcp_server.py"],
      "env": {
        "MIJIA_USERNAME": "your_username",
        "MIJIA_PASSWORD": "your_password"
      }
    }
  }
}
```

### Cline 集成

对于 Cline（原 Claude Dev），添加 MCP 服务器配置：

```json
{
  "mcp": {
    "servers": {
      "mijia": {
        "command": "python",
        "args": ["/path/to/miot-agent/mcp_server/mcp_server.py"],
        "env": {
          "MIJIA_USERNAME": "your_username",
          "MIJIA_PASSWORD": "your_password"
        }
      }
    }
  }
}
```

### 通用 MCP 客户端集成

对于任何兼容 MCP 的客户端：

1. **命令**: `python /path/to/miot-agent/mcp_server/mcp_server.py`
2. **环境变量**:
   - `MIJIA_USERNAME`: 米家账户用户名
   - `MIJIA_PASSWORD`: 米家账户密码
   - `MIJIA_ENABLE_QR`: 设置为 "true" 启用二维码登录（可选）
   - `MIJIA_LOG_LEVEL`: 日志级别（DEBUG, INFO, WARNING, ERROR）

### 验证集成

集成完成后，您应该能在 AI 助手中看到以下工具：

- **连接管理**: `connect`, `connect_with_qr`, `disconnect`, `ping`
- **设备管理**: `discover_devices`, `search_devices`
- **属性操作**: `get_property_value`, `set_property_value`, `batch_set_properties`
- **动作操作**: `call_action`
- **状态监控**: `get_device_status`, `refresh_all_device_status`
- **系统管理**: `get_server_status`, `clear_cache`

以及这些资源：
- `mijia://devices` - 设备列表
- `mijia://config` - 配置信息
- `mijia://device/{device_id}/properties` - 设备属性
- `mijia://device/{device_id}/actions` - 设备动作

## 工具使用指南

### 连接管理

#### 连接到米家云服务
```json
{
  "method": "tools/call",
  "params": {
    "name": "connect",
    "arguments": {}
  }
}
```

#### 断开连接
```json
{
  "method": "tools/call",
  "params": {
    "name": "disconnect",
    "arguments": {}
  }
}
```

### 设备发现和管理

#### 发现设备
```json
{
  "method": "tools/call",
  "params": {
    "name": "discover_devices",
    "arguments": {}
  }
}
```

#### 搜索设备
```json
{
  "method": "tools/call",
  "params": {
    "name": "search_devices",
    "arguments": {
      "name_filter": "台灯",
      "model_filter": "xiaomi",
      "online_only": true
    }
  }
}
```

### 设备属性操作

#### 获取设备属性列表
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

#### 获取属性值
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

#### 设置属性值
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

#### 批量设置属性
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

### 设备动作调用

#### 获取设备动作列表
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

#### 调用设备动作
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

### 状态监控

#### 获取设备状态
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

#### 刷新所有设备状态
```json
{
  "method": "tools/call",
  "params": {
    "name": "refresh_all_device_status",
    "arguments": {}
  }
}
```

#### 获取缓存状态
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

### 系统管理

#### 获取服务器状态
```json
{
  "method": "tools/call",
  "params": {
    "name": "get_server_status",
    "arguments": {}
  }
}
```

#### 清除缓存
```json
{
  "method": "tools/call",
  "params": {
    "name": "clear_cache",
    "arguments": {}
  }
}
```

#### 测试连通性
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

## 资源访问

### 获取设备列表
```json
{
  "method": "resources/read",
  "params": {
    "uri": "mijia://devices"
  }
}
```

### 获取配置信息
```json
{
  "method": "resources/read",
  "params": {
    "uri": "mijia://config"
  }
}
```

### 获取设备属性
```json
{
  "method": "resources/read",
  "params": {
    "uri": "mijia://device/123456789/properties"
  }
}
```

### 获取设备动作
```json
{
  "method": "resources/read",
  "params": {
    "uri": "mijia://device/123456789/actions"
  }
}
```

## 错误处理

所有工具调用都会返回统一的错误格式：

```json
{
  "success": false,
  "error": "错误描述",
  "error_code": "ERROR_CODE",
  "timestamp": "2024-01-01T12:00:00Z"
}
```

常见错误代码：
- `ADAPTER_NOT_INITIALIZED`: 适配器未初始化
- `DEVICE_NOT_FOUND`: 设备未找到
- `PROPERTY_NOT_FOUND`: 属性未找到
- `ACTION_NOT_FOUND`: 动作未找到
- `CONNECTION_FAILED`: 连接失败
- `AUTHENTICATION_FAILED`: 认证失败

## 日志配置

日志级别可以通过环境变量设置：

```bash
# 环境变量
export MIJIA_LOG_LEVEL="DEBUG"
```

## 项目结构

```
miot-agent/
├── adapter/
│   ├── mijia_adapter.py      # 米家适配器实现
│   └── mijia_config.py       # 配置管理
├── mcp_server/
│   ├── mcp_server.py         # MCP服务器主程序
│   └── server_config.json    # 服务器配置
├── requirements.txt          # 项目依赖
├── mcp_test.py              # 测试脚本
└── README.md                # 项目文档
```

## 开发指南

### 添加新工具

1. 在 `mcp_server.py` 中添加工具函数：

```python
@mcp.tool()
async def your_new_tool(param1: str, param2: int = 0) -> str:
    """工具描述
    
    Args:
        param1: 参数1描述
        param2: 参数2描述
    
    Returns:
        返回值描述
    """
    # 实现逻辑
    pass
```

2. 在 `server_config.json` 中添加工具配置：

```json
{
  "name": "your_new_tool",
  "description": "工具描述",
  "category": "category_name"
}
```

### 添加新资源

1. 在 `mcp_server.py` 中添加资源处理函数：

```python
@mcp.resource("mijia://your-resource")
async def get_your_resource() -> str:
    """资源描述"""
    # 实现逻辑
    pass
```

2. 在 `server_config.json` 中添加资源配置：

```json
{
  "uri": "mijia://your-resource",
  "name": "资源名称",
  "description": "资源描述",
  "mimeType": "application/json"
}
```

## 许可证

MIT License

## 贡献

欢迎提交 Issue 和 Pull Request！