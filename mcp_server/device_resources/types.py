"""Concrete device resource types."""

from __future__ import annotations

from typing import Any, Dict, List

from mcp_server.device_resources.base import BaseDeviceResource


class LightDeviceResource(BaseDeviceResource):
    resource_type = "lightDevice"
    label = "Light Device"
    supported_device_types = ["light", "ceiling-light", "ambient-light", "night-light", "bathroom-light", "light-strip"]
    supported_control_semantics = ["direct_lighting_device"]

    @classmethod
    def build(cls, device: Dict[str, Any], profile: Dict[str, Any]) -> Dict[str, Any]:
        resource = super().build(device, profile)
        writable_properties = profile.get("profile_driven_schema", {}).get("writable_properties", [])
        resource["usage"] |= {
            "primary_controls": ["power", "brightness", "color_temperature", "toggle"],
            "extended_property_controls": [
                item.get("name")
                for item in writable_properties
                if item.get("name") not in {"on", "brightness", "color-temperature"}
            ],
            "notes": [
                "This device behaves like a direct lighting endpoint.",
                "Brightness and color temperature should prefer the standard tools when available.",
            ],
        }
        return resource


class SwitchDeviceResource(BaseDeviceResource):
    resource_type = "switchDevice"
    label = "Switch Device"
    supported_device_types = ["switch"]
    supported_control_semantics = ["switch_device", "switch_channel_for_named_load"]

    @classmethod
    def build(cls, device: Dict[str, Any], profile: Dict[str, Any]) -> Dict[str, Any]:
        resource = super().build(device, profile)
        writable_properties = profile.get("profile_driven_schema", {}).get("writable_properties", [])
        notes: List[str] = ["This device is controlled like a switch endpoint."]
        if device.get("control_semantics") == "switch_channel_for_named_load":
            notes.append("This looks like a named load attached to a multi-gang wall switch channel.")
        resource["usage"] |= {
            "primary_controls": ["power", "toggle"],
            "extended_property_controls": [
                item.get("name")
                for item in writable_properties
                if item.get("name") != "on"
            ],
            "notes": notes,
        }
        return resource


class SensorDeviceResource(BaseDeviceResource):
    resource_type = "sensorDevice"
    label = "Sensor Device"
    supported_device_types = [
        "temperature-humidity-sensor",
        "temperature-sensor",
        "humidity-sensor",
        "motion-sensor",
        "contact-sensor",
        "smoke-sensor",
        "gas-sensor",
        "water-leak-sensor",
        "light-sensor",
    ]

    @classmethod
    def build(cls, device: Dict[str, Any], profile: Dict[str, Any]) -> Dict[str, Any]:
        resource = super().build(device, profile)
        readable_properties = profile.get("profile_driven_schema", {}).get("readable_properties", [])
        resource["usage"] |= {
            "primary_controls": [],
            "observable_properties": [
                {
                    "name": item.get("name"),
                    "description": item.get("description"),
                    "unit": item.get("unit"),
                }
                for item in readable_properties
            ],
            "notes": [
                "This device is primarily read-only.",
                "Use the observed state and readable properties as the main product interface.",
            ],
        }
        return resource


class GenericDeviceResource(BaseDeviceResource):
    resource_type = "genericDevice"
    label = "Generic Device"

    @classmethod
    def matches(cls, device: Dict[str, Any], profile: Dict[str, Any]) -> bool:
        return True

    @classmethod
    def build(cls, device: Dict[str, Any], profile: Dict[str, Any]) -> Dict[str, Any]:
        resource = super().build(device, profile)
        resource["usage"] |= {
            "primary_controls": [],
            "extended_property_controls": [
                item.get("name")
                for item in profile.get("profile_driven_schema", {}).get("writable_properties", [])
            ],
            "notes": [
                "No specialized device resource matched this device yet.",
                "Use profile-driven controls from writable properties or actions.",
            ],
        }
        return resource
