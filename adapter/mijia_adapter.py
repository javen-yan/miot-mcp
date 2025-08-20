"""基于 MijiaAPI 的米家设备适配器"""

import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from mijiaAPI import mijiaAPI, mijiaDevice, mijiaLogin
from config import load_mijia_config, MijiaConfig
import json

_LOGGER = logging.getLogger(__name__)

class DevProp(object):
    def __init__(self, prop_dict: dict):
        """
        初始化属性对象。

        Args:
            prop_dict (dict): 属性字典。

        Raises:
            ValueError: 如果属性类型不受支持。
        """
        self.name = prop_dict['name']
        self.desc = prop_dict['description']
        self.type = prop_dict['type']
        if self.type not in ['bool', 'int', 'uint', 'float', 'string']:
            raise ValueError(f'不支持的类型: {self.type}, 可选类型: bool, int, uint, float, string')
        self.rw = prop_dict['rw']
        self.unit = prop_dict['unit']
        self.range = prop_dict['range']
        self.value_list = prop_dict.get('value-list', None)
        self.method = prop_dict['method']

    def __str__(self):
        """
        返回属性的字符串表示。

        Returns:
            str: 属性的名称、描述、类型、读写权限、单位和范围。
        """
        lines = [
            f"  {self.name}: {self.desc}",
            f"    valuetype: {self.type}, rw: {self.rw}, unit: {self.unit}, range: {self.range}"
        ]

        if self.value_list:
            value_lines = [f"    {item['value']}: {item['description']}" for item in self.value_list]
            lines.extend(value_lines)

        return '\n'.join(lines)


class DevAction(object):
    def __init__(self, act_dict: dict):
        """
        初始化动作对象。

        Args:
            act_dict (dict): 动作字典。
        """
        self.name = act_dict['name']
        self.desc = act_dict['description']
        self.method = act_dict['method']

    def __str__(self):
        """
        返回动作的字符串表示。

        Returns:
            str: 动作的名称和描述。
        """
        return f'  {self.name}: {self.desc}'


class MijiaAdapter:
    """米家设备适配器"""
    
    def __init__(self):
        """初始化适配器"""
        self._api: Optional[mijiaAPI] = None
        self._auth_data: Optional[Dict[str, Any]] = None
        self._connected = False
        self._devices: Dict[str, mijiaDevice] = {}
        self._config: Optional[MijiaConfig] = load_mijia_config()
        
    async def connect(self) -> bool:
        """连接到米家云服务
            
        Returns:
            bool: 连接是否成功
        """
        try:
            if not self._config:
                raise ValueError("Mijia config not loaded")

            login = mijiaLogin()
            auth_data = self.load_auth_data()
            if auth_data:
                self._auth_data = auth_data
                _LOGGER.info("Loaded auth data from file")
            else:
                if self._config.enableQR:
                    # 使用 mijiaLogin 进行登录
                    self._auth_data = login.QRlogin()
                else:
                    self._auth_data = login.login(self._config.username, self._config.password)

                if self._auth_data:
                    self.save_auth_data(self._auth_data)
            
            # 使用认证数据初始化 API
            self._api = mijiaAPI(self._auth_data)
            
            # 检查 API 是否可用
            if self._api.available:
                self._connected = True
                _LOGGER.info("Successfully connected to Mijia cloud service")
                return True
            else:
                _LOGGER.error("API not available")
                return False
                
        except Exception as e:
            _LOGGER.error(f"Failed to connect to Mijia cloud service: {e}")
            return False
    
    async def disconnect(self):
        """断开连接"""
        try:
            self._api = None
            self._auth_data = None
            self._connected = False
            self._devices.clear()
            _LOGGER.info("Disconnected from Mijia cloud service")
        except Exception as e:
            _LOGGER.error(f"Error during disconnection: {e}")
    
    async def discover_devices(self) -> List[mijiaDevice]:
        """发现设备
        
        Returns:
            List[mijiaDevice]: 发现的设备列表
        """
        if not self._connected or not self._api:
            raise RuntimeError("Not connected to Mijia cloud service")
        
        try:
            # 获取设备列表
            raw_device_infos = self._api.get_devices_list()
            device_infos = []
            for device_data in raw_device_infos:
                did = device_data["did"]
                device = mijiaDevice(self._api, dev_info=device_data, did=did)
                self._devices[did] = device
                device_infos.append(device)
            _LOGGER.info(f"Discovered {len(device_infos)} devices: {[device.name for device in device_infos]}")
            return device_infos
            
        except Exception as e:
            _LOGGER.error(f"Failed to discover devices: {e}")
            raise

    def save_auth_data(self, auth_data: Dict[str, Any]):
        """保存认证数据"""
        with open('auth_data.json', 'w') as f:
            json.dump(auth_data, f)

    def load_auth_data(self) -> Optional[Dict[str, Any]]:
        """加载认证数据"""
        try:
            with open('auth_data.json', 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            return None
    
    async def get_device_properties(self, device_id: str) -> List[DevProp]:
        """获取设备属性列表
        
        Args:
            device_id: 设备ID
            
        Returns:
            List[DevProp]: 设备属性列表
        """
        device = self._get_device(device_id)
        
        try:
            # 获取设备规格信息
            propsMap = device.prop_list
            props = []
            for prop in propsMap:
                prop = DevProp(prop)
                props.append(prop)
            return props
        except Exception as e:
            _LOGGER.error(f"Failed to get device properties for {device_id}: {e}")
            raise
    
    async def get_device_actions(self, device_id: str) -> List[DevAction]:
        """获取设备操作列表
        
        Args:
            device_id: 设备ID
            
        Returns:
            List[ActionInfo]: 操作信息列表
        """
        if not self._connected:
            raise RuntimeError("未连接到米家云服务")
        
        if device_id not in self._devices:
            raise ValueError(f"设备 {device_id} 未找到")
        
        try:
            device = self._devices[device_id]
            actionsMap = device.action_list
            actions = []
            for act in actionsMap:
                actions.append(DevAction(act))
            return actions
        except Exception as e:
            _LOGGER.error(f"获取设备操作失败: {e}")
            raise
    
    async def get_property_value(self, device_id: str, siid: int, piid: int) -> Any:
        """获取设备属性值
        
        Args:
            device_id: 设备ID
            siid: 服务实例ID
            piid: 属性实例ID
            
        Returns:
            Any: 属性值
        """
        if not self._connected:
            raise RuntimeError("未连接到米家云服务")
        
        try:
            # 使用 API 直接获取属性
            result = self._api.get_devices_prop([{
                "did": device_id,
                "siid": siid,
                "piid": piid
            }])
            
            if result and len(result) > 0:
                prop_result = result[0]
                if prop_result.get('code') == 0:
                    return prop_result.get('value')
                else:
                    raise RuntimeError(f"获取属性失败: {prop_result.get('code')}")
            else:
                raise RuntimeError("未返回结果")
                
        except Exception as e:
            _LOGGER.error(f"获取属性值失败: {e}")
            raise
    
    async def set_property_value(self, device_id: str, siid: int, piid: int, value: Any) -> bool:
        """设置设备属性值
        
        Args:
            device_id: 设备ID
            siid: 服务实例ID
            piid: 属性实例ID
            value: 要设置的值
            
        Returns:
            bool: 设置是否成功
        """
        if not self._connected:
            raise RuntimeError("未连接到米家云服务")
        
        try:
            # 使用 API 直接设置属性
            result = self._api.set_devices_prop([{
                "did": device_id,
                "siid": siid,
                "piid": piid,
                "value": value
            }])
            
            if result and len(result) > 0:
                prop_result = result[0]
                success = prop_result.get('code') == 0
                if success:
                    _LOGGER.info(f"成功设置属性 {siid}:{piid} = {value} (设备: {device_id})")
                else:
                    _LOGGER.warning(f"设置属性失败 {siid}:{piid} = {value} (设备: {device_id}), 错误码: {prop_result.get('code')}")
                return success
            else:
                return False
                
        except Exception as e:
            _LOGGER.error(f"设置属性值失败: {e}")
            raise
    
    async def call_action(self, device_id: str, siid: int, aiid: int, params: Optional[List[Any]] = None) -> List[Any]:
        """执行设备操作
        
        Args:
            device_id: 设备ID
            siid: 服务实例ID
            aiid: 操作实例ID
            params: 操作参数
            
        Returns:
            List[Any]: 操作结果
        """
        if not self._connected:
            raise RuntimeError("未连接到米家云服务")
        
        try:
            # 使用 API 直接执行操作
            result = self._api.run_action({
                "did": device_id,
                "siid": siid,
                "aiid": aiid,
                "in": params or []
            })
            
            if result.get('code') == 0:
                _LOGGER.info(f"成功执行操作 {siid}:{aiid} (设备: {device_id})")
                return result.get('out', [])
            else:
                raise RuntimeError(f"操作执行失败，错误码: {result.get('code')}")
                
        except Exception as e:
            _LOGGER.error(f"执行操作失败: {e}")
            raise
    
    def _get_device(self, device_id: str) -> mijiaDevice:
        """获取设备对象
        
        Args:
            device_id: 设备ID
            
        Returns:
            mijiaDevice: 设备对象
            
        Raises:
            RuntimeError: 如果设备不存在或未连接
        """
        if not self._connected:
            raise RuntimeError("Not connected to Mijia cloud service")
        
        if device_id not in self._devices:
            raise RuntimeError(f"Device {device_id} not found. Please discover devices first.")
        
        return self._devices[device_id]
    
    @property
    def connected(self) -> bool:
        """是否已连接"""
        return self._connected
    
    @property
    def device_count(self) -> int:
        """设备数量"""
        return len(self._devices)