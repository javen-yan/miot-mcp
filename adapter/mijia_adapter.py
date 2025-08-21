"""Mijia device adapter based on MijiaAPI"""

import logging
from typing import Dict, List, Any, Optional
from mijiaAPI import mijiaAPI, mijiaDevice, mijiaLogin
from config.mijia_config import load_mijia_config, MijiaConfig
import json
import traceback
from datetime import datetime

_LOGGER = logging.getLogger(__name__)

class DevProp(object):
    def __init__(self, prop_dict: dict):
        """
    Initialize property object.

    Args:
        prop_dict (dict): Property dictionary.

    Raises:
        ValueError: If property type is not supported.
    """
        self.name = prop_dict['name']
        self.desc = prop_dict['description']
        self.type = prop_dict['type']
        if self.type not in ['bool', 'int', 'uint', 'float', 'string']:
            raise ValueError(f'Unsupported type: {self.type}, available types: bool, int, uint, float, string')
        self.rw = prop_dict['rw']
        self.unit = prop_dict['unit']
        self.range = prop_dict['range']
        self.value_list = prop_dict.get('value-list', None)
        self.method = prop_dict['method']

    def __str__(self):
        """
    Return string representation of the property.

    Returns:
        str: Property name, description, type, read/write permissions, unit and range.
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
    Initialize action object.

    Args:
        act_dict (dict): Action dictionary.
    """
        self.name = act_dict['name']
        self.desc = act_dict['description']
        self.method = act_dict['method']

    def __str__(self):
        """
    Return string representation of the action.

    Returns:
        str: Action name and description.
    """
        return f'  {self.name}: {self.desc}'


class MijiaAdapter:
    """Mijia device adapter"""

    def __init__(self):
        """Initialize adapter"""
        self._api: Optional[mijiaAPI] = None
        self._auth_data: Optional[Dict[str, Any]] = None
        self._connected = False
        self._devices: Dict[str, mijiaDevice] = {}
        self._config: Optional[MijiaConfig] = None
        self._device_status_cache: Dict[str, Dict[str, Any]] = {}
        self._last_status_update: Optional[datetime] = None
        self._config = load_mijia_config()
        
    async def connect(self) -> bool:
        """Connect to Mijia cloud service

        Returns:
            bool: Whether connection is successful
        """
        try:
            _LOGGER.info("Starting connection to Mijia cloud service...")
            
            if not self._config:
                error_msg = "Mijia configuration not loaded, please check config file or environment variables"
                _LOGGER.error(error_msg)
                raise ValueError(error_msg)

            login = mijiaLogin()
            auth_data = self.load_auth_data()
            
            if auth_data:
                self._auth_data = auth_data
                _LOGGER.info("Successfully loaded authentication data from file")
            else:
                _LOGGER.info("No cached authentication data found, starting login...")
                
                if self._config.enableQR:
                    _LOGGER.info("Using QR code login mode")
                    self._auth_data = login.QRlogin()
                else:
                    _LOGGER.info(f"Using username/password login: {self._config.username}")
                    if not self._config.username or not self._config.password:
                        error_msg = "Username or password is empty, please check configuration"
                        _LOGGER.error(error_msg)
                        raise ValueError(error_msg)
                    
                    self._auth_data = login.login(self._config.username, self._config.password)

                if self._auth_data:
                    self.save_auth_data(self._auth_data)
                    _LOGGER.info("Login successful, authentication data saved")
                else:
                    error_msg = "Login failed, authentication data not obtained"
                    _LOGGER.error(error_msg)
                    raise RuntimeError(error_msg)
            
            # 使用认证数据初始化 API
            _LOGGER.info("Initializing Mijia API...")
            self._api = mijiaAPI(self._auth_data)
            
            # 检查 API 是否可用
            if self._api.available:
                self._connected = True
                _LOGGER.info("Successfully connected to Mijia cloud service")
                return True
            else:
                error_msg = "Mijia API unavailable, possibly due to expired authentication data or network issues"
                _LOGGER.error(error_msg)
                # 清除可能过期的认证数据
                self._auth_data = None
                try:
                    import os
                    if os.path.exists('auth_data.json'):
                        os.remove('auth_data.json')
                        _LOGGER.info("Expired authentication data file cleared")
                except Exception as cleanup_e:
                    _LOGGER.warning(f"Failed to clear authentication data file: {cleanup_e}")
                
                raise RuntimeError(error_msg)
                
        except Exception as e:
            error_msg = f"Failed to connect to Mijia cloud service: {str(e)}"
            _LOGGER.error(error_msg)
            _LOGGER.debug(f"Detailed error information: {traceback.format_exc()}")
            
            # 重置连接状态
            self._connected = False
            self._api = None
            
            return False
    
    async def disconnect(self):
        """Disconnect"""
        try:
            self._api = None
            self._auth_data = None
            self._connected = False
            self._devices.clear()
            _LOGGER.info("Disconnected from Mijia cloud service")
        except Exception as e:
            _LOGGER.error(f"Error during disconnection: {e}")
    
    async def discover_devices(self) -> List[mijiaDevice]:
        """Discover devices

        Returns:
            List[mijiaDevice]: List of discovered devices
        """
        if not self._connected or not self._api:
            error_msg = "Not connected to Mijia cloud service, please call connect() method first"
            _LOGGER.error(error_msg)
            raise RuntimeError(error_msg)
        
        try:
            _LOGGER.info("Starting Mijia device discovery...")
            
            # 获取设备列表
            raw_device_infos = self._api.get_devices_list()
            
            if not raw_device_infos:
                _LOGGER.warning("No devices discovered")
                return []
            
            _LOGGER.info(f"Retrieved {len(raw_device_infos)} device information from cloud")
            
            device_infos = []
            failed_devices = []
            
            for i, device_data in enumerate(raw_device_infos):
                try:
                    did = device_data.get("did")
                    if not did:
                        _LOGGER.warning(f"Device {i} missing did field, skipping")
                        failed_devices.append(f"Device{i}(missing did)")
                        continue
                    
                    device = mijiaDevice(self._api, dev_info=device_data, did=did)
                    self._devices[did] = device
                    device_infos.append(device)
                    
                    _LOGGER.debug(f"Successfully created device object: {device.name} ({did})")
                    
                except Exception as device_e:
                    device_name = device_data.get('name', f'Device{i}')
                    _LOGGER.warning(f"Failed to create device object {device_name}: {device_e}")
                    failed_devices.append(device_name)
                    continue
            
            success_count = len(device_infos)
            failed_count = len(failed_devices)
            
            if success_count > 0:
                device_names = [device.name for device in device_infos]
                _LOGGER.info(f"Successfully discovered {success_count} devices: {device_names}")
            
            if failed_count > 0:
                _LOGGER.warning(f"{failed_count} devices failed to create: {failed_devices}")
            
            return device_infos
            
        except Exception as e:
            error_msg = f"Failed to discover devices: {str(e)}"
            _LOGGER.error(error_msg)
            _LOGGER.debug(f"Detailed error information: {traceback.format_exc()}")
            raise RuntimeError(error_msg) from e

    def _save_auth_data(self, auth_data: Dict[str, Any]):
        """Save authentication data"""
        with open('auth_data.json', 'w') as f:
            json.dump(auth_data, f)

    def _load_auth_data(self) -> Optional[Dict[str, Any]]:
        """Load authentication data"""
        try:
            with open('auth_data.json', 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            return None
    
    async def get_device_properties(self, device_id: str) -> List[DevProp]:
        """Get device property list

        Args:
            device_id: Device ID

        Returns:
            List[DevProp]: Device property list
        """
        device = self._get_device(device_id)
        
        try:
            # Get device specification information
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
        """Get device action list

        Args:
            device_id: Device ID

        Returns:
            List[DevAction]: Device action list
        """
        if not self._connected:
            raise RuntimeError("Not connected to Mijia cloud service")
        
        if device_id not in self._devices:
            raise ValueError(f"Device {device_id} not found")
        
        try:
            device = self._devices[device_id]
            actionsMap = device.action_list
            actions = []
            for act in actionsMap:
                actions.append(DevAction(act))
            return actions
        except Exception as e:
            _LOGGER.error(f"Failed to get device operations: {e}")
            raise
    
    async def get_property_value(self, device_id: str, siid: int, piid: int) -> Any:
        """Get device property value

        Args:
            device_id: Device ID
            siid: Service instance ID
            piid: Property instance ID

        Returns:
            Any: Property value
        """
        if not self._connected:
            raise RuntimeError("Not connected to Mijia cloud service")
        
        try:
            # Use API to get property directly
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
                    raise RuntimeError(f"Failed to get property: {prop_result.get('code')}")
            else:
                raise RuntimeError("No result returned")
                
        except Exception as e:
            _LOGGER.error(f"Failed to get property value: {e}")
            raise
    
    async def set_property_value(self, device_id: str, siid: int, piid: int, value: Any) -> bool:
        """Set device property value

        Args:
            device_id: Device ID
            siid: Service instance ID
            piid: Property instance ID
            value: Value to set

        Returns:
            bool: Whether setting is successful
        """
        if not self._connected:
            raise RuntimeError("Not connected to Mijia cloud service")
        
        try:
            # Use API to set property directly
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
                    _LOGGER.info(f"Successfully set property {siid}:{piid} = {value} (device: {device_id})")
                else:
                    _LOGGER.warning(f"Failed to set property {siid}:{piid} = {value} (device: {device_id}), error code: {prop_result.get('code')}")
                return success
            else:
                return False
                
        except Exception as e:
            _LOGGER.error(f"Failed to set property value: {e}")
            raise
    
    async def call_action(self, device_id: str, siid: int, aiid: int, params: List[Any] = None) -> List[Any]:
        """Execute device action

        Args:
            device_id: Device ID
            siid: Service instance ID
            aiid: Action instance ID
            params: Action parameters

        Returns:
            List[Any]: Action result
        """
        if not self._connected:
            raise RuntimeError("Not connected to Mijia cloud service")
        
        try:
            # Use API to execute action directly
            result = self._api.run_action({
                "did": device_id,
                "siid": siid,
                "aiid": aiid,
                "in": params or []
            })
            
            if result.get('code') == 0:
                _LOGGER.info(f"Successfully executed action {siid}:{aiid} (device: {device_id})")
                return result.get('out', [])
            else:
                raise RuntimeError(f"Action execution failed, error code: {result.get('code')}")
                
        except Exception as e:
            _LOGGER.error(f"Failed to execute action: {e}")
            raise
    
    def _get_device(self, device_id: str) -> mijiaDevice:
        """Get device object

        Args:
            device_id: Device ID

        Returns:
            mijiaDevice: Device object

        Raises:
            RuntimeError: If device does not exist or not connected
        """
        if not self._connected:
            raise RuntimeError("Not connected to Mijia cloud service")
        
        if device_id not in self._devices:
            raise RuntimeError(f"Device {device_id} not found. Please discover devices first.")
        
        return self._devices[device_id]
    
    @property
    def connected(self) -> bool:
        """Whether connected"""
        return self._connected
    
    @property
    def device_count(self) -> int:
        """Device count"""
        return len(self._devices)
    
    async def get_device_status(self, device_id: str) -> Dict[str, Any]:
        """Get device status information

        Args:
            device_id: Device ID

        Returns:
            Dict[str, Any]: Device status information
        """
        if not self._connected:
            raise RuntimeError("Not connected to Mijia cloud service")
        
        try:
            device = self._get_device(device_id)
            
            # Get device basic information
            status_info = {
                "device_id": device_id,
                "name": device.name,
                "model": device.model,
                "online": getattr(device, 'online', True),
                "room_id": getattr(device, 'room_id', None),
                "spec_type": getattr(device, 'spec_type', None),
                "last_update": datetime.now().isoformat()
            }
            
            # Cache status information
            self._device_status_cache[device_id] = status_info
            self._last_status_update = datetime.now()
            
            _LOGGER.debug(f"Successfully retrieved device status: {device.name} ({device_id})")
            return status_info
            
        except Exception as e:
            error_msg = f"Failed to get device status {device_id}: {str(e)}"
            _LOGGER.error(error_msg)
            _LOGGER.debug(f"Detailed error information: {traceback.format_exc()}")
            raise RuntimeError(error_msg) from e
    
    async def refresh_all_device_status(self) -> Dict[str, Dict[str, Any]]:
        """Refresh all device status

        Returns:
            Dict[str, Dict[str, Any]]: Status information of all devices
        """
        if not self._connected:
            raise RuntimeError("Not connected to Mijia cloud service")
        
        try:
            _LOGGER.info("Starting to refresh all device status...")
            
            status_results = {}
            failed_devices = []
            
            for device_id in self._devices.keys():
                try:
                    status = await self.get_device_status(device_id)
                    status_results[device_id] = status
                except Exception as e:
                    _LOGGER.warning(f"Failed to refresh device status {device_id}: {e}")
                    failed_devices.append(device_id)
                    continue
            
            success_count = len(status_results)
            failed_count = len(failed_devices)
            
            _LOGGER.info(f"Device status refresh completed: {success_count} successful, {failed_count} failed")
            
            if failed_count > 0:
                _LOGGER.warning(f"Failed to refresh devices: {failed_devices}")
            
            return status_results
            
        except Exception as e:
            error_msg = f"Failed to refresh all device status: {str(e)}"
            _LOGGER.error(error_msg)
            _LOGGER.debug(f"Detailed error information: {traceback.format_exc()}")
            raise RuntimeError(error_msg) from e
    
    def get_cached_device_status(self, device_id: str) -> Optional[Dict[str, Any]]:
        """Get cached device status

        Args:
            device_id: Device ID

        Returns:
            Optional[Dict[str, Any]]: Cached device status, returns None if not exists
        """
        return self._device_status_cache.get(device_id)
    
    def get_all_cached_device_status(self) -> Dict[str, Dict[str, Any]]:
        """Get all cached device status

        Returns:
            Dict[str, Dict[str, Any]]: All cached device status
        """
        return self._device_status_cache.copy()
    
    def clear_status_cache(self) -> int:
        """Clear status cache

        Returns:
            int: Number of cleared cache items
        """
        cache_count = len(self._device_status_cache)
        self._device_status_cache.clear()
        self._last_status_update = None
        _LOGGER.info(f"Cleared {cache_count} device status caches")
        return cache_count
    
    @property
    def last_status_update(self) -> Optional[datetime]:
        """Last status update time"""
        return self._last_status_update