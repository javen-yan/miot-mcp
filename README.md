# Miot Agent - 米家设备智能控制代理

基于 MijiaAPI 的米家设备智能控制代理，提供标准化的 AI Agent 工具接口，支持动态设备发现、属性读写和动作调用。

## 特性

- 🔌 **简化架构**: 基于 MijiaAPI 2.0+ 的轻量级实现
- 🤖 **AI Agent 兼容**: 标准化工具注册和调用接口
- 🔍 **动态发现**: 自动发现和管理米家设备
- ⚡ **异步支持**: 全异步操作，高性能并发
- 🛠️ **灵活配置**: 支持配置文件和环境变量
- 📝 **完整日志**: 详细的操作日志和错误处理
- 🏗️ **模块化设计**: 清晰的适配器、代理层和配置管理分离

## 安装

### 1. 克隆项目

```bash
git clone <repository-url>
cd miot-agent
```

### 2. 创建虚拟环境

```bash
python3 -m venv .venv
source .venv/bin/activate  # Linux/Mac
# 或
.venv\Scripts\activate     # Windows
```

### 3. 安装依赖

```bash
pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/
```

## 配置

### 方式一：配置文件

1. 复制配置模板：
```bash
cp config/mijia.yaml.example config/mijia.yaml
```

2. 编辑配置文件：
```yaml
mijia:
  username: "your_username"  # 米家账号
  password: "your_password"  # 密码
  enableQR: false
```

### 方式二：环境变量

```bash
export MIJIA_USERNAME="your_username"
export MIJIA_PASSWORD="your_password"
export MIJIA_ENABLEQR="false"
```
## API 参考

#### 连接管理

- `connect()` - 连接到米家云服务
- `disconnect()` - 断开连接 

#### 设备管理

- `discover_devices()` - 发现设备
- `get_device_properties(device_id)` - 获取设备属性列表
- `get_device_actions(device_id)` - 获取设备动作列表

#### 设备控制

- `get_property_value(device_id, siid, piid)` - 读取属性值
- `set_property_value(device_id, siid, piid, value)` - 设置属性值
- `call_action(device_id, siid, aiid, params)` - 调用设备动作

### 工具注册系统

```python
from agent_layer.tool_registry import tool_registry

# 获取所有工具
tools = tool_registry.get_tools()

# 获取米家工具
mijia_tools = tool_registry.get_tools_by_category('mijia')

# 执行工具
result = await tool_registry.execute_tool('connect', {})

# 导出 OpenAI 格式
openai_tools = tool_registry.get_openai_tools()
```

## 项目结构

```
miot-agent/
├── adapter/                 # 设备适配器层
│   ├── __init__.py
│   └── mijia_adapter.py     # MijiaAPI 适配器实现
├── agent_layer/             # AI Agent 工具层
│   ├── __init__.py
│   └── tool_registry.py     # 工具注册和管理系统
├── config/                  # 配置管理模块
│   ├── __init__.py
│   └── mijia_config.py      # 米家配置管理
├── examples/                # 示例代码
│   └── __init__.py
├── .gitignore              # Git 忽略文件
├── requirements.txt         # 项目依赖
├── setup.py                # 安装配置
├── test_mijia.py           # 测试文件
└── README.md               # 项目文档
```


## 常见问题

### Q: 连接失败怎么办？

A: 请检查：
1. 账号密码是否正确
2. 网络连接是否正常
3. 用户名和密码可能需要发送验证码，推荐使用二维码登录

### Q: 找不到设备怎么办？

A: 请确认：
1. 设备已添加到米家APP
2. 设备在线状态正常
3. 账号有设备访问权限

### Q: 属性读写失败？

A: 可能原因：
1. 设备离线
2. 属性不支持读写操作
3. 参数格式不正确
4. 设备权限限制

## 开发

### 添加自定义工具

```python
from agent_layer.tool_registry import tool_function, tool_registry

@tool_function(name="my_tool", description="我的自定义工具", category="custom")
async def my_custom_tool(param1: str, param2: int) -> dict:
    """自定义工具实现"""
    return {"result": f"处理 {param1} 和 {param2}"}

# 工具会自动注册到 tool_registry
```

### 扩展设备适配器

```python
from adapter.mijia_adapter import MijiaAdapter

class CustomMijiaAdapter(MijiaAdapter):
    async def custom_method(self):
        """自定义方法"""
        # 实现自定义逻辑
        pass
```

## 许可证

MIT License

## 贡献

欢迎提交 Issue 和 Pull Request！

## 更新日志

### v0.1.0
- 重构架构，使用 MijiaAPI 作为底层
- 完善工具注册和调用机制