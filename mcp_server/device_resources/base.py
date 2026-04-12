"""Base classes for product-facing device resources."""

from __future__ import annotations

from typing import Any, Dict, List


class BaseDeviceResource:
    """Product-facing device resource built from a normalized device + profile."""

    resource_type = "base"
    label = "Base Device"
    supported_device_types: List[str] = []
    supported_control_semantics: List[str] = []

    @classmethod
    def matches(cls, device: Dict[str, Any], profile: Dict[str, Any]) -> bool:
        device_type = str(device.get("device_type") or "")
        control_semantics = str(device.get("control_semantics") or "")
        if cls.supported_control_semantics and control_semantics in cls.supported_control_semantics:
            return True
        if cls.supported_device_types and device_type in cls.supported_device_types:
            return True
        return False

    @classmethod
    def build(cls, device: Dict[str, Any], profile: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "resource_type": cls.resource_type,
            "label": cls.label,
            "device_type": device.get("device_type"),
            "control_semantics": device.get("control_semantics"),
            "location": device.get("location"),
            "online": device.get("online"),
            "control_model": cls.build_control_model(profile),
            "observed_state": cls.build_observed_state(profile),
            "usage": cls.build_usage(profile),
        }

    @classmethod
    def build_control_model(cls, profile: Dict[str, Any]) -> Dict[str, Any]:
        standard_capabilities = profile.get("standard_capability_schema", {}).get("capabilities", [])
        standard_operations = [
            item for item in profile.get("supported_operations", [])
            if item.get("enabled") and item.get("operation") not in {"set_property", "run_action"}
        ]
        profile_driven = profile.get("profile_driven_schema", {})

        return {
            "mode": "profile_backed",
            "standard_capabilities": [
                {
                    "name": item.get("name"),
                    "label": item.get("label"),
                    "kind": item.get("kind"),
                    "backing_name": item.get("backing_name"),
                }
                for item in standard_capabilities
            ],
            "standard_operations": [
                {
                    "operation": item.get("operation"),
                    "preferred_tool": item.get("preferred_tool"),
                }
                for item in standard_operations
            ],
            "generic_operations": profile_driven.get("generic_operations", {}),
        }

    @classmethod
    def build_observed_state(cls, profile: Dict[str, Any]) -> Dict[str, Any]:
        state = profile.get("state", {})
        return {
            "values": state,
            "summary": profile.get("state_summary", {}),
        }

    @classmethod
    def build_usage(cls, profile: Dict[str, Any]) -> Dict[str, Any]:
        profile_driven = profile.get("profile_driven_schema", {})
        return {
            "preferred_strategy": "Use standard operations first. Fall back to profile-driven set_property/run_action when needed.",
            "writable_property_names": [
                item.get("name")
                for item in profile_driven.get("writable_properties", [])
            ],
            "action_names": [
                item.get("name")
                for item in profile_driven.get("actions", [])
            ],
        }
