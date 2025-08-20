"""AI Agent 工具注册模块"""

from typing import Dict, List, Any, Callable, Optional
from dataclasses import dataclass, field
from functools import wraps
import inspect
import json
import logging
from ..adapter import MijiaAdapter

_LOGGER = logging.getLogger(__name__)

@dataclass
class ToolParameter:
    """工具参数定义"""
    name: str
    type: str
    description: str
    required: bool = True
    enum: Optional[List[Any]] = None
    minimum: Optional[float] = None
    maximum: Optional[float] = None
    default: Optional[Any] = None


@dataclass
class ToolDefinition:
    """工具定义"""
    name: str
    description: str
    parameters: List[ToolParameter] = field(default_factory=list)
    function: Optional[Callable] = None
    category: str = "general"
    
    def to_openai_schema(self) -> Dict[str, Any]:
        """转换为 OpenAI Function Calling 格式"""
        properties = {}
        required = []
        
        for param in self.parameters:
            param_schema = {
                "type": param.type,
                "description": param.description
            }
            
            if param.enum:
                param_schema["enum"] = param.enum
            if param.minimum is not None:
                param_schema["minimum"] = param.minimum
            if param.maximum is not None:
                param_schema["maximum"] = param.maximum
            if param.default is not None:
                param_schema["default"] = param.default
            
            properties[param.name] = param_schema
            
            if param.required:
                required.append(param.name)
        
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required
                }
            }
        }


class ToolRegistry:
    """工具注册表"""
    
    def __init__(self):
        self._tools: Dict[str, ToolDefinition] = {}
        self._categories: Dict[str, List[str]] = {}
    
    def register_tool(self, tool_def: ToolDefinition) -> None:
        """注册工具"""
        self._tools[tool_def.name] = tool_def
        
        if tool_def.category not in self._categories:
            self._categories[tool_def.category] = []
        self._categories[tool_def.category].append(tool_def.name)
        
        _LOGGER.info(f"Registered tool: {tool_def.name} in category {tool_def.category}")
    
    def get_tool(self, name: str) -> Optional[ToolDefinition]:
        """获取工具定义"""
        return self._tools.get(name)
    
    def get_tools(self) -> List[ToolDefinition]:
        """获取所有工具"""
        return list(self._tools.values())
    
    def get_tools_by_category(self, category: str) -> List[ToolDefinition]:
        """根据分类获取工具"""
        tool_names = self._categories.get(category, [])
        return [self._tools[name] for name in tool_names if name in self._tools]
    
    def get_openai_tools(self) -> List[Dict[str, Any]]:
        """获取 OpenAI Function Calling 格式的工具列表"""
        return [tool.to_openai_schema() for tool in self._tools.values()]
    
    def get_tool_names(self) -> List[str]:
        """获取所有工具名称"""
        return list(self._tools.keys())
    
    def get_categories(self) -> List[str]:
        """获取所有分类"""
        return list(self._categories.keys())
    
    async def execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """执行工具函数"""
        tool = self.get_tool(tool_name)
        if not tool:
            raise ValueError(f"Tool '{tool_name}' not found")
        
        if not tool.function:
            raise ValueError(f"Tool '{tool_name}' has no associated function")
        
        try:
            # 验证参数
            validated_params = self._validate_parameters(tool, parameters)
            
            # 执行函数
            if inspect.iscoroutinefunction(tool.function):
                result = await tool.function(**validated_params)
            else:
                result = tool.function(**validated_params)
            
            return {
                "success": True,
                "result": result,
                "tool_name": tool_name
            }
        
        except Exception as e:
            _LOGGER.error(f"Error executing tool {tool_name}: {e}")
            return {
                "success": False,
                "error": str(e),
                "tool_name": tool_name
            }
    
    def _validate_parameters(self, tool: ToolDefinition, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """验证工具参数"""
        validated = {}
        
        # 检查必需参数
        for param in tool.parameters:
            if param.required and param.name not in parameters:
                raise ValueError(f"Required parameter '{param.name}' is missing")
            
            if param.name in parameters:
                value = parameters[param.name]
                
                # 类型检查
                if not self._validate_type(value, param.type):
                    raise ValueError(f"Parameter '{param.name}' must be of type {param.type}")
                
                # 枚举检查
                if param.enum and value not in param.enum:
                    raise ValueError(f"Parameter '{param.name}' must be one of {param.enum}")
                
                # 数值范围检查
                if param.minimum is not None and isinstance(value, (int, float)) and value < param.minimum:
                    raise ValueError(f"Parameter '{param.name}' must be >= {param.minimum}")
                
                if param.maximum is not None and isinstance(value, (int, float)) and value > param.maximum:
                    raise ValueError(f"Parameter '{param.name}' must be <= {param.maximum}")
                
                validated[param.name] = value
            
            elif param.default is not None:
                validated[param.name] = param.default
        
        return validated
    
    def _validate_type(self, value: Any, expected_type: str) -> bool:
        """验证参数类型"""
        type_mapping = {
            "string": str,
            "integer": int,
            "number": (int, float),
            "boolean": bool,
            "array": list,
            "object": dict
        }
        
        expected_python_type = type_mapping.get(expected_type)
        if expected_python_type is None:
            return True  # 未知类型，跳过验证
        
        return isinstance(value, expected_python_type)
    
    def export_schema(self, format: str = "openai") -> str:
        """导出工具 schema"""
        if format == "openai":
            return json.dumps(self.get_openai_tools(), indent=2, ensure_ascii=False)
        else:
            raise ValueError(f"Unsupported format: {format}")


def tool_function(name: str = None, description: str = None, category: str = "general"):
    """工具函数装饰器"""
    def decorator(func: Callable) -> Callable:
        # 获取函数信息
        func_name = name or func.__name__
        func_description = description or func.__doc__ or f"Execute {func_name}"
        
        # 解析函数参数
        sig = inspect.signature(func)
        parameters = []
        
        for param_name, param in sig.parameters.items():
            if param_name == 'self':
                continue
            
            param_type = "string"  # 默认类型
            param_description = f"Parameter {param_name}"
            required = param.default == inspect.Parameter.empty
            default_value = None if required else param.default
            
            # 尝试从类型注解获取类型信息
            if param.annotation != inspect.Parameter.empty:
                if param.annotation == int:
                    param_type = "integer"
                elif param.annotation == float:
                    param_type = "number"
                elif param.annotation == bool:
                    param_type = "boolean"
                elif param.annotation == list:
                    param_type = "array"
                elif param.annotation == dict:
                    param_type = "object"
            
            parameters.append(ToolParameter(
                name=param_name,
                type=param_type,
                description=param_description,
                required=required,
                default=default_value
            ))
        
        # 创建工具定义
        tool_def = ToolDefinition(
            name=func_name,
            description=func_description,
            parameters=parameters,
            function=func,
            category=category
        )
        
        # 将工具定义附加到函数
        func._tool_definition = tool_def
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        
        wrapper._tool_definition = tool_def
        return wrapper
    
    return decorator


# 全局工具注册表实例
tool_registry = ToolRegistry()

# 全局米家适配器实例
_adapter: Optional[MijiaAdapter] = None


def get_adapter() -> MijiaAdapter:
    """获取米家适配器实例"""
    global _adapter
    if _adapter is None:
        raise RuntimeError("Mijia adapter not initialized. Please call initialize_adapter first.")
    return _adapter


def initialize_adapter(username: str, password: str, region: str = "cn") -> None:
    """初始化米家适配器"""
    global _adapter
    _adapter = MijiaAdapter(username, password, region)


# 米家设备控制工具
@tool_function(name="connect", description="连接到米家云服务", category="mijia")
async def connect() -> Dict[str, Any]:
    """连接到米家云服务"""
    adapter = get_adapter()
    success = await adapter.connect()
    return {
        "connected": success,
        "message": "Connected to Mijia cloud service" if success else "Failed to connect"
    }


@tool_function(name="disconnect", description="断开米家云服务连接", category="mijia")
async def disconnect() -> Dict[str, Any]:
    """断开米家云服务连接"""
    adapter = get_adapter()
    await adapter.disconnect()
    return {
        "connected": False,
        "message": "Disconnected from Mijia cloud service"
    }


@tool_function(name="discover_devices", description="发现米家设备", category="mijia")
async def discover_devices() -> Dict[str, Any]:
    """发现米家设备"""
    adapter = get_adapter()
    devices = await adapter.discover_devices()
    return {
        "devices": [{
            "device_id": d.device_id,
            "name": d.name,
            "model": d.model,
            "room_id": d.room_id,
            "online": d.online
        } for d in devices],
        "count": len(devices)
    }


@tool_function(name="get_device_properties", description="获取设备属性列表", category="mijia")
async def get_device_properties(device_id: str) -> Dict[str, Any]:
    """获取设备属性列表"""
    adapter = get_adapter()
    properties = await adapter.get_device_properties(device_id)
    return {
        "device_id": device_id,
        "properties": [{
            "siid": p.siid,
            "piid": p.piid,
            "name": p.name,
            "description": p.description,
            "access": p.access,
            "format": p.format,
            "value_range": p.value_range,
            "value_list": p.value_list,
            "unit": p.unit
        } for p in properties]
    }


@tool_function(name="get_device_actions", description="获取设备动作列表", category="mijia")
async def get_device_actions(device_id: str) -> Dict[str, Any]:
    """获取设备动作列表"""
    adapter = get_adapter()
    actions = await adapter.get_device_actions(device_id)
    return {
        "device_id": device_id,
        "actions": [{
            "siid": a.siid,
            "aiid": a.aiid,
            "name": a.name,
            "description": a.description,
            "in_params": a.in_params,
            "out_params": a.out_params
        } for a in actions]
    }


@tool_function(name="get_property_value", description="获取设备属性值", category="mijia")
async def get_property_value(device_id: str, siid: int, piid: int) -> Dict[str, Any]:
    """获取设备属性值"""
    adapter = get_adapter()
    value = await adapter.get_property_value(device_id, siid, piid)
    return {
        "device_id": device_id,
        "siid": siid,
        "piid": piid,
        "value": value
    }


@tool_function(name="set_property_value", description="设置设备属性值", category="mijia")
async def set_property_value(device_id: str, siid: int, piid: int, value: Any) -> Dict[str, Any]:
    """设置设备属性值"""
    adapter = get_adapter()
    success = await adapter.set_property_value(device_id, siid, piid, value)
    return {
        "device_id": device_id,
        "siid": siid,
        "piid": piid,
        "value": value,
        "success": success
    }


@tool_function(name="call_action", description="调用设备动作", category="mijia")
async def call_action(device_id: str, siid: int, aiid: int, params: Optional[List[Any]] = None) -> Dict[str, Any]:
    """调用设备动作"""
    adapter = get_adapter()
    result = await adapter.call_action(device_id, siid, aiid, params)
    return {
        "device_id": device_id,
        "siid": siid,
        "aiid": aiid,
        "params": params,
        "result": result
    }


# 自动注册米家工具
for name, obj in globals().items():
    if hasattr(obj, '_tool_definition'):
        tool_registry.register_tool(obj._tool_definition)