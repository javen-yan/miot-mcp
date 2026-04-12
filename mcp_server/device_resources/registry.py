"""Registry for device resource models."""

from __future__ import annotations

from typing import Any, Dict, List, Type

from mcp_server.device_resources.base import BaseDeviceResource
from mcp_server.device_resources.types import (
    GenericDeviceResource,
    LightDeviceResource,
    SensorDeviceResource,
    SwitchDeviceResource,
)


DEVICE_RESOURCE_TYPES: List[Type[BaseDeviceResource]] = [
    SwitchDeviceResource,
    LightDeviceResource,
    SensorDeviceResource,
    GenericDeviceResource,
]


def build_device_resource(device: Dict[str, Any], profile: Dict[str, Any]) -> Dict[str, Any]:
    for resource_type in DEVICE_RESOURCE_TYPES:
        if resource_type.matches(device, profile):
            return resource_type.build(device, profile)
    return GenericDeviceResource.build(device, profile)
