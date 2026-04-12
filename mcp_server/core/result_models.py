"""Pydantic output models for MCP tool schemas."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class MCPResultModel(BaseModel):
    """Base structured payload returned by tools."""

    model_config = ConfigDict(extra="allow")

    success: bool = Field(description="Whether the tool completed successfully.")
    message: str = Field(description="Short human-readable result summary.")
    error: Optional[Dict[str, Any]] = Field(default=None, description="Structured error details when the tool fails.")


class ServiceStatusResult(MCPResultModel):
    service: Optional[Dict[str, Any]] = Field(default=None, description="Current service metadata and connection state.")
    action: Optional[str] = Field(default=None, description="Action taken by the server, if any.")
    assistant_summary: Optional[str] = Field(default=None, description="Short login-oriented summary for AI clients.")
    next_steps: Optional[Dict[str, Any]] = Field(default=None, description="Suggested next tools or actions.")


class HomeListResult(MCPResultModel):
    homes: Optional[List[Dict[str, Any]]] = Field(default=None, description="Homes returned by the server.")
    home_count: Optional[int] = Field(default=None, description="Number of homes in the result.")
    device_count: Optional[int] = Field(default=None, description="Number of devices included or available.")
    assistant_summary: Optional[str] = Field(default=None, description="Friendly summary for AI clients.")
    next_steps: Optional[Dict[str, Any]] = Field(default=None, description="Suggested follow-up tools or actions.")
    response_mode: Optional[str] = Field(default=None, description="Summary/full response mode hint.")


class ToolCatalogResult(MCPResultModel):
    everyday_tools: Optional[List[Dict[str, Any]]] = Field(default=None, description="Recommended tools for the common path.")
    advanced_tools: Optional[List[Dict[str, Any]]] = Field(default=None, description="Advanced or lower-level tools.")
    recommended_workflow: Optional[List[Dict[str, Any]]] = Field(default=None, description="Suggested end-to-end invocation path.")
    guidance: Optional[str] = Field(default=None, description="Additional client guidance.")


class DeviceListResult(MCPResultModel):
    devices: Optional[List[Dict[str, Any]]] = Field(default=None, description="Matching devices.")
    count: Optional[int] = Field(default=None, description="Number of matching devices.")
    response_mode: Optional[str] = Field(default=None, description="Summary/full response mode hint.")


class DeviceResult(MCPResultModel):
    device: Optional[Dict[str, Any]] = Field(default=None, description="Resolved device summary.")
    profile: Optional[Dict[str, Any]] = Field(default=None, description="Device profile or summarized profile payload.")
    response_mode: Optional[str] = Field(default=None, description="Summary/full response mode hint.")


class DeviceStatusResult(MCPResultModel):
    device: Optional[Dict[str, Any]] = Field(default=None, description="Resolved device summary.")
    device_resource: Optional[Dict[str, Any]] = Field(default=None, description="Resource-style device description for clients.")
    state: Optional[Dict[str, Any]] = Field(default=None, description="Current observed device state.")
    state_summary: Optional[str] = Field(default=None, description="Short natural-language state summary.")
    supported_operations: Optional[List[Dict[str, Any]]] = Field(default=None, description="Supported operations for this device.")
    assistant_summary: Optional[str] = Field(default=None, description="User-facing summary for AI agents.")
    quick_actions: Optional[List[str]] = Field(default=None, description="Suggested quick operations.")
    next_steps: Optional[Dict[str, Any]] = Field(default=None, description="Suggested follow-up tools or actions.")
    response_mode: Optional[str] = Field(default=None, description="Summary/full response mode hint.")


class DeviceCapabilitiesResult(MCPResultModel):
    device: Optional[Dict[str, Any]] = Field(default=None, description="Resolved device summary.")
    primary_domain: Optional[str] = Field(default=None, description="Primary device capability domain.")
    device_domains: Optional[List[str]] = Field(default=None, description="All detected device domains.")
    capability_families: Optional[List[str]] = Field(default=None, description="Grouped capability families.")
    capability_schema: Optional[Dict[str, Any]] = Field(default=None, description="Standardized capability schema.")
    capability_catalog: Optional[Dict[str, Any]] = Field(default=None, description="Catalog of standard capabilities and intents.")
    mapping_report: Optional[Dict[str, Any]] = Field(default=None, description="Detailed mapping report in verbose mode.")
    profile_driven_schema: Optional[Dict[str, Any]] = Field(default=None, description="Profile-derived writable properties and actions.")
    device_resource: Optional[Dict[str, Any]] = Field(default=None, description="Resource-style device description.")
    supported_operations: Optional[List[Dict[str, Any]]] = Field(default=None, description="Enabled operations for this device.")
    state: Optional[Dict[str, Any]] = Field(default=None, description="Raw device state in verbose mode.")
    state_summary: Optional[str] = Field(default=None, description="Short natural-language state summary.")
    mapping_summary: Optional[Dict[str, Any]] = Field(default=None, description="Coverage summary for mapped capabilities.")
    response_mode: Optional[str] = Field(default=None, description="Summary/full response mode hint.")


class ControlResult(MCPResultModel):
    device: Optional[Dict[str, Any]] = Field(default=None, description="Resolved target device.")
    execution: Optional[Dict[str, Any]] = Field(default=None, description="Execution details for the requested control.")
    previous_state: Optional[Dict[str, Any]] = Field(default=None, description="Observed state before control.")
    current_state: Optional[Dict[str, Any]] = Field(default=None, description="Observed state after control.")
    state: Optional[Dict[str, Any]] = Field(default=None, description="Current device state after control.")
    outcome: Optional[Dict[str, Any]] = Field(default=None, description="High-level outcome summary.")
    assistant_summary: Optional[str] = Field(default=None, description="Natural-language summary of what changed.")


class SceneListResult(MCPResultModel):
    scenes: Optional[List[Dict[str, Any]]] = Field(default=None, description="Matching scenes.")
    count: Optional[int] = Field(default=None, description="Number of scenes in the result.")


class SceneExecutionResult(MCPResultModel):
    scene: Optional[Dict[str, Any]] = Field(default=None, description="Resolved scene metadata.")
    executed: Optional[bool] = Field(default=None, description="Whether the scene run call succeeded.")


class ConsumableItemsResult(MCPResultModel):
    items: Optional[List[Dict[str, Any]]] = Field(default=None, description="Consumable items returned from Mijia.")
    count: Optional[int] = Field(default=None, description="Number of consumable items.")


class IntentControlResult(MCPResultModel):
    route: Optional[str] = Field(default=None, description="Routing decision taken by the intent controller.")
    parsed_intent: Optional[Dict[str, Any]] = Field(default=None, description="Parsed intent details inferred from the query.")
    result: Optional[Dict[str, Any]] = Field(default=None, description="Structured result from the routed tool.")
    fallback_mode: Optional[str] = Field(default=None, description="Fallback mode used when standard routing did not apply.")
    fallback_result: Optional[Dict[str, Any]] = Field(default=None, description="Structured result from the fallback path.")


class PingResult(MCPResultModel):
    server: Optional[str] = Field(default=None, description="Server identifier that handled the request.")
