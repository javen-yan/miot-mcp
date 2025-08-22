#!/usr/bin/env python3
"""Mijia MCP server implementation based on FastMCP

Use FastMCP framework to simplify MCP server implementation, avoiding the complexity of low-level stdio processing.
"""

import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add project root directory to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from mcp.server.fastmcp import FastMCP
from adapter.mijia_adapter import MijiaAdapter
from config.mijia_config import load_mijia_config

# Load environment configuration
default_config = load_mijia_config()

# Configure logging - use stderr to avoid interfering with stdio communication
logging.basicConfig(
    level=default_config.log_level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stderr  # Important: use stderr instead of stdout
)
logger = logging.getLogger(__name__)

# Create FastMCP server instance
mcp = FastMCP("mijia-mcp-server")

# Global adapter instance
_adapter: Optional[MijiaAdapter] = None

# Resource cache
_resource_cache: Dict[str, Any] = {}


def get_adapter() -> Optional[MijiaAdapter]:
    """Get adapter instance"""
    global _adapter
    if _adapter is None:
        try:
            _adapter = MijiaAdapter()
            logger.info("Mijia adapter created successfully")
        except Exception as e:
            logger.error(f"Failed to create Mijia adapter: {e}")
    return _adapter


def device_to_dict(device) -> Dict[str, Any]:
    """Convert mijiaDevice object to dictionary for JSON serialization
    
    Args:
        device: mijiaDevice object
        
    Returns:
        Dict containing device information
    """
    try:
        return {
            "did": getattr(device, 'did', None),
            "name": getattr(device, 'name', None),
            "model": getattr(device, 'model', None),
            "online": getattr(device, 'online', True),
            "room_id": getattr(device, 'room_id', None),
            "spec_type": getattr(device, 'spec_type', None),
            "token": getattr(device, 'token', None),
            "ip": getattr(device, 'ip', None),
            "mac": getattr(device, 'mac', None)
        }
    except Exception as e:
        logger.warning(f"Failed to convert device to dict: {e}")
        return {
            "did": str(device) if device else None,
            "name": "Unknown Device",
            "error": str(e)
        }


@mcp.resource("mijia://devices")
async def get_devices_resource() -> str:
    """Get device list resource

    Returns:
        JSON string of device list
    """
    adapter = get_adapter()
    if not adapter:
        return json.dumps({
            "error": "Adapter not initialized",
            "devices": []
        }, ensure_ascii=False, indent=2)
    
    try:
        if not adapter.connected:
            await adapter.connect()
        
        devices = await adapter.discover_devices()
        # Convert mijiaDevice objects to dictionaries for JSON serialization
        device_list = [device_to_dict(device) for device in devices]
        
        result = {
            "devices": device_list,
            "count": len(device_list),
            "timestamp": asyncio.get_event_loop().time()
        }
        
        # Cache result
        _resource_cache["devices"] = result
        
        return json.dumps(result, ensure_ascii=False, indent=2)
        
    except Exception as e:
        logger.error(f"Failed to get device list: {e}")
        return json.dumps({
            "error": str(e),
            "devices": []
        }, ensure_ascii=False, indent=2)


@mcp.resource("mijia://config")
async def get_config_resource() -> str:
    """Get configuration resource

    Returns:
        JSON string of configuration information
    """
    adapter = get_adapter()
    if not adapter:
        return json.dumps({
            "error": "Adapter not initialized",
            "connected": False
        }, ensure_ascii=False, indent=2)
    
    try:
        config_info = {
            "connected": adapter.connected,
            "device_count": adapter.device_count,
            "server_info": {
                "name": "mijia-mcp-server",
                "version": "1.0.1",
                "capabilities": ["tools", "resources"]
            },
            "timestamp": asyncio.get_event_loop().time()
        }
        
        # Cache result
        _resource_cache["config"] = config_info
        
        return json.dumps(config_info, ensure_ascii=False, indent=2)
        
    except Exception as e:
        logger.error(f"Failed to get configuration: {e}")
        return json.dumps({
            "error": str(e),
            "connected": False
        }, ensure_ascii=False, indent=2)


@mcp.resource("mijia://device/{device_id}/properties")
async def get_device_properties_resource(device_id: str) -> str:
    """Get device properties resource

    Args:
        device_id: Device ID

    Returns:
        JSON string of device properties
    """
    adapter = get_adapter()
    if not adapter:
        return json.dumps({
            "error": "Adapter not initialized",
            "device_id": device_id,
            "properties": []
        }, ensure_ascii=False, indent=2)
    
    try:
        properties = await adapter.get_device_properties(device_id)
        prop_list = []
        for prop in properties:
            prop_info = {
                "name": prop.name,
                "description": prop.desc,
                "type": prop.type,
                "rw": prop.rw,
                "unit": prop.unit,
                "range": prop.range,
                "value_list": prop.value_list,
                "method": prop.method
            }
            prop_list.append(prop_info)
        
        result = {
            "device_id": device_id,
            "properties": prop_list,
            "count": len(prop_list),
            "timestamp": asyncio.get_event_loop().time()
        }
        
        # Cache result
        _resource_cache[f"device_{device_id}_properties"] = result
        
        return json.dumps(result, ensure_ascii=False, indent=2)
        
    except Exception as e:
        logger.error(f"Failed to get device properties: {e}")
        return json.dumps({
            "error": str(e),
            "device_id": device_id,
            "properties": []
        }, ensure_ascii=False, indent=2)


@mcp.resource("mijia://device/{device_id}/actions")
async def get_device_actions_resource(device_id: str) -> str:
    """Get device actions resource

    Args:
        device_id: Device ID

    Returns:
        JSON string of device actions
    """
    adapter = get_adapter()
    if not adapter:
        return json.dumps({
            "error": "Adapter not initialized",
            "device_id": device_id,
            "actions": []
        }, ensure_ascii=False, indent=2)
    
    try:
        actions = await adapter.get_device_actions(device_id)
        action_list = []
        for action in actions:
            action_info = {
                "name": action.name,
                "description": action.desc,
                "method": action.method
            }
            action_list.append(action_info)
        
        result = {
            "device_id": device_id,
            "actions": action_list,
            "count": len(action_list),
            "timestamp": asyncio.get_event_loop().time()
        }
        
        # Cache result
        _resource_cache[f"device_{device_id}_actions"] = result
        
        return json.dumps(result, ensure_ascii=False, indent=2)
        
    except Exception as e:
        logger.error(f"Failed to get device actions: {e}")
        return json.dumps({
            "error": str(e),
            "device_id": device_id,
            "actions": []
        }, ensure_ascii=False, indent=2)


@mcp.tool()
async def connect() -> str:
    """Connect to Mijia cloud service

    Returns:
        JSON string of connection result
    """
    adapter = get_adapter()
    if not adapter:
        return json.dumps({
            "success": False,
            "error": "Adapter not initialized"
        }, ensure_ascii=False, indent=2)
    
    try:
        result = await _adapter.connect()
        return json.dumps({
            "success": result,
            "message": "Connection operation completed"
        }, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Connection failed: {e}")
        return json.dumps({
            "success": False,
            "error": str(e)
        }, ensure_ascii=False, indent=2)

@mcp.tool()
async def disconnect() -> str:
    """Disconnect from Mijia cloud service

    Returns:
        JSON string of disconnection result
    """
    adapter = get_adapter()
    if not adapter:
        return json.dumps({
            "success": False,
            "error": "Adapter not initialized"
        }, ensure_ascii=False, indent=2)

    try:
        await _adapter.disconnect()
        return json.dumps({
            "success": True,
            "message": "Disconnect operation completed"
        }, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Disconnection failed: {e}")
        return json.dumps({
            "success": False,
            "error": str(e)
        }, ensure_ascii=False, indent=2)


@mcp.tool()
async def discover_devices() -> str:
    """Discover Mijia devices

    Returns:
        JSON string of device list
    """
    adapter = get_adapter()
    if not adapter:
        return json.dumps({
            "success": False,
            "error": "Adapter not initialized"
        }, ensure_ascii=False, indent=2)
    try:
        devices = await _adapter.discover_devices()
        # Convert mijiaDevice objects to dictionaries for JSON serialization
        device_dicts = [device_to_dict(device) for device in devices]
        return json.dumps({
            "success": True,
            "devices": device_dicts,
            "count": len(device_dicts)
        }, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Device discovery failed: {e}")
        return json.dumps({
            "success": False,
            "error": str(e)
        }, ensure_ascii=False, indent=2)


@mcp.tool()
async def get_device_properties(device_id: str) -> str:
    """Get device properties

    Args:
        device_id: Device ID

    Returns:
        JSON string of device properties
    """
    adapter = get_adapter()
    if not adapter:
        return json.dumps({
            "success": False,
            "error": "Adapter not initialized"
        }, ensure_ascii=False, indent=2)
    
    try:
        properties = await adapter.get_device_properties(device_id)
        return json.dumps({
            "success": True,
            "device_id": device_id,
            "properties": properties
        }, ensure_ascii=False, indent=2)
        
    except Exception as e:
        logger.error(f"Failed to get device properties: {e}")
        return json.dumps({
            "success": False,
            "error": str(e)
        }, ensure_ascii=False, indent=2)


@mcp.tool()
async def get_device_actions(device_id: str) -> str:
    """Get device available actions

    Args:
        device_id: Device ID

    Returns:
        JSON string of device action list
    """
    adapter = get_adapter()
    if not adapter:
        return json.dumps({
            "success": False,
            "error": "Adapter not initialized"
        }, ensure_ascii=False, indent=2)
    
    try:
        actions = await adapter.get_device_actions(device_id)
        return json.dumps({
            "success": True,
            "device_id": device_id,
            "actions": actions
        }, ensure_ascii=False, indent=2)
        
    except Exception as e:
        logger.error(f"Failed to get device actions: {e}")
        return json.dumps({
            "success": False,
            "error": str(e)
        }, ensure_ascii=False, indent=2)


@mcp.tool()
async def set_property_value(device_id: str, siid: int, piid: int, value: Any) -> str:
    """Set device property value

    Args:
        device_id: Device ID
        siid: Service instance ID
        piid: Property instance ID
        value: Value to set

    Returns:
        JSON string of setting result
    """
    adapter = get_adapter()
    if not adapter:
        return json.dumps({
            "success": False,
            "error": "Adapter not initialized"
        }, ensure_ascii=False, indent=2)
    
    try:
        result = await adapter.set_property_value(device_id, siid, piid, value)
        return json.dumps({
            "success": True,
            "device_id": device_id,
            "siid": siid,
            "piid": piid,
            "value": value,
            "result": result
        }, ensure_ascii=False, indent=2)
        
    except Exception as e:
        logger.error(f"Failed to set property value: {e}")
        return json.dumps({
            "success": False,
            "error": str(e)
        }, ensure_ascii=False, indent=2)


@mcp.tool()
async def call_action(device_id: str, siid: int, aiid: int, params: List[Any] = None) -> str:
    """Call device action

    Args:
        device_id: Device ID
        siid: Service instance ID
        aiid: Action instance ID
        params: Action parameter list (optional)

    Returns:
        JSON string of action call result
    """
    adapter = get_adapter()
    if not adapter:
        return json.dumps({
            "success": False,
            "error": "Adapter not initialized"
        }, ensure_ascii=False, indent=2)
    
    if params is None:
        params = []
    
    try:
        result = await adapter.call_action(device_id, siid, aiid, params)
        return json.dumps({
            "success": True,
            "device_id": device_id,
            "siid": siid,
            "aiid": aiid,
            "params": params,
            "result": result
        }, ensure_ascii=False, indent=2)
        
    except Exception as e:
        logger.error(f"Failed to call action: {e}")
        return json.dumps({
            "success": False,
            "error": str(e)
        }, ensure_ascii=False, indent=2)


@mcp.tool()
async def get_property_value(device_id: str, siid: int, piid: int) -> str:
    """Get device property value

    Args:
        device_id: Device ID
        siid: Service instance ID
        piid: Property instance ID

    Returns:
        JSON string of property value
    """
    adapter = get_adapter()
    if not adapter:
        return json.dumps({
            "success": False,
            "error": "Adapter not initialized"
        }, ensure_ascii=False, indent=2)
    
    try:
        value = await adapter.get_property_value(device_id, siid, piid)
        return json.dumps({
            "success": True,
            "device_id": device_id,
            "siid": siid,
            "piid": piid,
            "value": value
        }, ensure_ascii=False, indent=2)
        
    except Exception as e:
        logger.error(f"Failed to get property value: {e}")
        return json.dumps({
            "success": False,
            "error": str(e)
        }, ensure_ascii=False, indent=2)


@mcp.tool()
async def batch_set_properties(operations: List[Dict[str, Any]]) -> str:
    """Batch set device properties

    Args:
        operations: Operation list, each operation contains device_id, siid, piid, value

    Returns:
        JSON string of batch operation result
    """
    adapter = get_adapter()
    if not adapter:
        return json.dumps({
            "success": False,
            "error": "Adapter not initialized"
        }, ensure_ascii=False, indent=2)
    
    results = []
    success_count = 0
    
    for i, op in enumerate(operations):
        try:
            device_id = op.get('device_id')
            siid = op.get('siid')
            piid = op.get('piid')
            value = op.get('value')
            
            if not all([device_id, siid is not None, piid is not None, value is not None]):
                results.append({
                    "index": i,
                    "success": False,
                    "error": "missing required parameters"
                })
                continue
            
            result = await adapter.set_property_value(device_id, siid, piid, value)
            results.append({
                "index": i,
                "device_id": device_id,
                "siid": siid,
                "piid": piid,
                "value": value,
                "success": result
            })
            
            if result:
                success_count += 1
                
        except Exception as e:
            logger.error(f"Batch operation item {i} failed: {e}")
            results.append({
                "index": i,
                "success": False,
                "error": str(e)
            })
    
    return json.dumps({
        "success": success_count > 0,
        "total": len(operations),
        "success_count": success_count,
        "failed_count": len(operations) - success_count,
        "results": results
    }, ensure_ascii=False, indent=2)


@mcp.tool()
async def search_devices(query: str = "", device_type: str = "", online_only: bool = False) -> str:
    """Search and filter devices

    Args:
        query: Search keywords (device name or model)
        device_type: Device type filter
        online_only: Whether to show only online devices

    Returns:
        JSON string of search results
    """
    adapter = get_adapter()
    if not adapter:
        return json.dumps({
            "success": False,
            "error": "Adapter not initialized"
        }, ensure_ascii=False, indent=2)
    
    try:
        if not adapter.connected:
            await adapter.connect()
        
        devices = await adapter.discover_devices()
        filtered_devices = []
        
        for device in devices:
            # 名称或型号匹配
            if query and query.lower() not in (device.name.lower() + " " + device.model.lower()):
                continue
            
            # 设备类型过滤
            if device_type and device_type.lower() not in device.model.lower():
                continue
            
            # 在线状态过滤
            if online_only and not getattr(device, 'online', True):
                continue
            
            device_info = {
                "did": device.did,
                "name": device.name,
                "model": device.model,
                "online": getattr(device, 'online', True),
                "room_id": getattr(device, 'room_id', None),
                "spec_type": getattr(device, 'spec_type', None)
            }
            filtered_devices.append(device_info)
        
        return json.dumps({
            "success": True,
            "query": query,
            "device_type": device_type,
            "online_only": online_only,
            "devices": filtered_devices,
            "count": len(filtered_devices),
            "total_devices": len(devices)
        }, ensure_ascii=False, indent=2)
        
    except Exception as e:
        logger.error(f"Device search failed: {e}")
        return json.dumps({
            "success": False,
            "error": str(e)
        }, ensure_ascii=False, indent=2)


@mcp.tool()
async def get_server_status() -> str:
    """Get server status information

    Returns:
        JSON string of server status
    """
    adapter = get_adapter()
    
    status_info = {
        "server": {
            "name": "mijia-mcp-server",
            "version": "1.0.1",
            "uptime": asyncio.get_event_loop().time(),
            "capabilities": ["tools", "resources"]
        },
        "adapter": {
            "initialized": adapter is not None,
            "connected": adapter.connected if adapter else False,
            "device_count": adapter.device_count if adapter else 0
        },
        "cache": {
            "resource_count": len(_resource_cache),
            "cached_resources": list(_resource_cache.keys())
        },
        "timestamp": asyncio.get_event_loop().time()
    }
    
    return json.dumps(status_info, ensure_ascii=False, indent=2)


@mcp.tool()
async def clear_cache() -> str:
    """Clear resource cache

    Returns:
        JSON string of clear result
    """
    global _resource_cache
    cache_count = len(_resource_cache)
    _resource_cache.clear()
    
    return json.dumps({
        "success": True,
        "message": f"Cache cleared, {cache_count} items removed",
        "cleared_count": cache_count
    }, ensure_ascii=False, indent=2)


@mcp.tool()
async def get_device_status(device_id: str) -> str:
    """Get device status information

    Args:
        device_id: Device ID

    Returns:
        JSON string of device status
    """
    adapter = get_adapter()
    if not adapter:
        return json.dumps({
            "success": False,
            "error": "Adapter not initialized"
        }, ensure_ascii=False, indent=2)
    
    try:
        status = await adapter.get_device_status(device_id)
        return json.dumps({
            "success": True,
            "status": status
        }, ensure_ascii=False, indent=2)
        
    except Exception as e:
        logger.error(f"Failed to get device status: {e}")
        return json.dumps({
            "success": False,
            "error": str(e)
        }, ensure_ascii=False, indent=2)


@mcp.tool()
async def refresh_all_device_status() -> str:
    """Refresh all device status

    Returns:
        JSON string of all device status
    """
    adapter = get_adapter()
    if not adapter:
        return json.dumps({
            "success": False,
            "error": "Adapter not initialized"
        }, ensure_ascii=False, indent=2)
    
    try:
        status_results = await adapter.refresh_all_device_status()
        return json.dumps({
            "success": True,
            "device_count": len(status_results),
            "status_results": status_results,
            "last_update": adapter.last_status_update.isoformat() if adapter.last_status_update else None
        }, ensure_ascii=False, indent=2)
        
    except Exception as e:
        logger.error(f"Failed to refresh all device status: {e}")
        return json.dumps({
            "success": False,
            "error": str(e)
        }, ensure_ascii=False, indent=2)


@mcp.tool()
async def get_cached_device_status(device_id: str = "") -> str:
    """Get cached device status

    Args:
        device_id: Device ID, if empty returns all cached status

    Returns:
        JSON string of cached status
    """
    adapter = get_adapter()
    if not adapter:
        return json.dumps({
            "success": False,
            "error": "Adapter not initialized"
        }, ensure_ascii=False, indent=2)
    
    try:
        if device_id:
            # get cached status
            cached_status = adapter.get_cached_device_status(device_id)
            return json.dumps({
                "success": True,
                "device_id": device_id,
                "cached_status": cached_status,
                "found": cached_status is not None
            }, ensure_ascii=False, indent=2)
        else:
            # get all cached status
            all_cached = adapter.get_all_cached_status()
            return json.dumps({
                "success": True,
                "cached_count": len(all_cached),
                "all_cached_status": all_cached,
                "last_update": adapter.last_status_update.isoformat() if adapter.last_status_update else None
            }, ensure_ascii=False, indent=2)
        
    except Exception as e:
        logger.error(f"Failed to get cached status: {e}")
        return json.dumps({
            "success": False,
            "error": str(e)
        }, ensure_ascii=False, indent=2)


@mcp.tool()
async def clear_status_cache() -> str:
    """Clear device status cache

    Returns:
        JSON string of clear result
    """
    adapter = get_adapter()
    if not adapter:
        return json.dumps({
            "success": False,
            "error": "Adapter not initialized"
        }, ensure_ascii=False, indent=2)
    
    try:
        cleared_count = adapter.clear_status_cache()
        return json.dumps({
            "success": True,
            "message": f"Cleared {cleared_count} device status cache entries",
            "cleared_count": cleared_count
        }, ensure_ascii=False, indent=2)
        
    except Exception as e:
        logger.error(f"Failed to clear status cache: {e}")
        return json.dumps({
            "success": False,
            "error": str(e)
        }, ensure_ascii=False, indent=2)


@mcp.tool()
async def get_homes() -> str:
    """Get home list

    Returns:
        JSON string of home list
    """
    adapter = get_adapter()
    if not adapter:
        return json.dumps({
            "success": False,
            "error": "Adapter not initialized"
        }, ensure_ascii=False, indent=2)
    
    try:
        if not adapter.connected:
            await adapter.connect()
        
        homes = await adapter.get_homes()
        return json.dumps({
            "success": True,
            "homes": homes,
            "count": len(homes)
        }, ensure_ascii=False, indent=2)
        
    except Exception as e:
        logger.error(f"Failed to get homes: {e}")
        return json.dumps({
            "success": False,
            "error": str(e)
        }, ensure_ascii=False, indent=2)


@mcp.tool()
async def get_scenes_list(home_id: str) -> str:
    """Get scene list for a specific home

    Args:
        home_id: Home ID

    Returns:
        JSON string of scene list
    """
    adapter = get_adapter()
    if not adapter:
        return json.dumps({
            "success": False,
            "error": "Adapter not initialized"
        }, ensure_ascii=False, indent=2)
    
    try:
        if not adapter.connected:
            await adapter.connect()
        
        scenes = await adapter.get_scenes_list(home_id)
        return json.dumps({
            "success": True,
            "home_id": home_id,
            "scenes": scenes,
            "count": len(scenes)
        }, ensure_ascii=False, indent=2)
        
    except Exception as e:
        logger.error(f"Failed to get scenes list: {e}")
        return json.dumps({
            "success": False,
            "error": str(e)
        }, ensure_ascii=False, indent=2)


@mcp.tool()
async def run_scene(scene_id: str) -> str:
    """Run a specific scene

    Args:
        scene_id: Scene ID

    Returns:
        JSON string of execution result
    """
    adapter = get_adapter()
    if not adapter:
        return json.dumps({
            "success": False,
            "error": "Adapter not initialized"
        }, ensure_ascii=False, indent=2)
    
    try:
        if not adapter.connected:
            await adapter.connect()
        
        result = await adapter.run_scene(scene_id)
        return json.dumps({
            "success": True,
            "scene_id": scene_id,
            "executed": result
        }, ensure_ascii=False, indent=2)
        
    except Exception as e:
        logger.error(f"Failed to run scene: {e}")
        return json.dumps({
            "success": False,
            "error": str(e)
        }, ensure_ascii=False, indent=2)


@mcp.tool()
async def get_consumable_items(home_id: str, owner_id: int = None) -> str:
    """Get consumable items for a specific home

    Args:
        home_id: Home ID
        owner_id: Owner ID (optional, for shared homes)

    Returns:
        JSON string of consumable items list
    """
    adapter = get_adapter()
    if not adapter:
        return json.dumps({
            "success": False,
            "error": "Adapter not initialized"
        }, ensure_ascii=False, indent=2)
    
    try:
        if not adapter.connected:
            await adapter.connect()
        
        items = await adapter.get_consumable_items(home_id, owner_id)
        return json.dumps({
            "success": True,
            "home_id": home_id,
            "owner_id": owner_id,
            "items": items,
            "count": len(items)
        }, ensure_ascii=False, indent=2)
        
    except Exception as e:
        logger.error(f"Failed to get consumable items: {e}")
        return json.dumps({
            "success": False,
            "error": str(e)
        }, ensure_ascii=False, indent=2)


@mcp.tool()
async def ping(message: str = "hello") -> str:
    """Test server connectivity

    Args:
        message: Message to send

    Returns:
        JSON string of response message
    """
    return json.dumps({
        "success": True,
        "message": f"pong: {message}",
        "timestamp": asyncio.get_event_loop().time(),
        "server": "mijia-mcp-server"
    }, ensure_ascii=False, indent=2)


def main():
    """Main entry point for the MCP server"""
    # Initialize adapter
    logger.info("Initializing Mijia adapter...")
    adapter = get_adapter()
    if not adapter:
        logger.error("Failed to initialize Mijia adapter")
        exit(1)
    # Start server
    logger.info("Starting MCP server...")
    mcp.run()


if __name__ == "__main__":
    main()