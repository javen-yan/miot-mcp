#!/usr/bin/env python3
"""Productized Mijia MCP server built on top of mijia-api 3.x."""

import sys
from contextlib import asynccontextmanager
from io import TextIOWrapper
from pathlib import Path
from typing import Annotated, Any, Dict, List, Optional

import anyio
import mcp.server.fastmcp.server as fastmcp_server_module
import mcp.types as types
from anyio.streams.memory import MemoryObjectReceiveStream, MemoryObjectSendStream
from mcp.server.fastmcp import FastMCP
from mcp.shared.message import SessionMessage

# Add project root directory to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from adapter.mijia_adapter import MijiaAdapter
from config.mijia_config import load_mijia_config
from mcp_server.core.capability_engine import (
    build_capability_mapping_report,
    build_device_capability_profile,
    build_profile_driven_schema,
    build_standard_capability_definition,
    build_standard_capability_schema,
    coerce_value_for_target,
    describe_supported_operations,
    summarize_capabilities,
)
from mcp_server.core.errors import (
    build_error_result,
    build_resource_result,
    build_result,
    extract_structured_content,
)
from mcp_server.core.result_models import (
    ConsumableItemsResult,
    ControlResult,
    DeviceCapabilitiesResult,
    DeviceListResult,
    DeviceResult,
    DeviceStatusResult,
    HomeListResult,
    IntentControlResult,
    PingResult,
    SceneExecutionResult,
    SceneListResult,
    ServiceStatusResult,
    ToolCatalogResult,
)
from mcp_server.core.intent_engine import infer_intent
from mcp_server.core.normalizers import (
    dedupe_actions,
    dedupe_properties,
    normalize_device,
    normalize_device_summary,
    normalize_home,
    normalize_scene,
)
from mcp_server.device_resources import build_device_resource
from mcp_server.device_definitions.intent_definitions import get_intent_catalog
from mcp_server.device_definitions.standard_capabilities import (
    OPERATION_CAPABILITY_MAP,
    get_capability_catalog,
    get_capability_definition,
)
from utils.logger import get_logger, setup_logging

SERVER_NAME = "mijia-mcp-server"
SERVER_VERSION = "2.0.0"
FALLBACK_ROOM_HINTS = ["客厅", "卧室", "书房", "厨房", "卫生间", "浴室", "阳台", "餐厅", "主卧", "次卧", "儿童房", "老人房", "玄关"]
READ_MOSTLY_DEVICE_TYPES = {
    "temperature-humidity-sensor",
    "temperature-sensor",
    "humidity-sensor",
    "motion-sensor",
    "contact-sensor",
    "smoke-sensor",
    "gas-sensor",
    "water-leak-sensor",
    "light-sensor",
}

# Load environment configuration
default_config = load_mijia_config()

# Setup logging and get log file path
log_file_path = setup_logging(default_config.log_level)
logger = get_logger(__name__)

ServiceStatusToolResult = Annotated[types.CallToolResult, ServiceStatusResult]
HomeListToolResult = Annotated[types.CallToolResult, HomeListResult]
ToolCatalogToolResult = Annotated[types.CallToolResult, ToolCatalogResult]
DeviceListToolResult = Annotated[types.CallToolResult, DeviceListResult]
DeviceToolResult = Annotated[types.CallToolResult, DeviceResult]
DeviceStatusToolResult = Annotated[types.CallToolResult, DeviceStatusResult]
DeviceCapabilitiesToolResult = Annotated[types.CallToolResult, DeviceCapabilitiesResult]
ControlToolResult = Annotated[types.CallToolResult, ControlResult]
SceneListToolResult = Annotated[types.CallToolResult, SceneListResult]
SceneExecutionToolResult = Annotated[types.CallToolResult, SceneExecutionResult]
ConsumableItemsToolResult = Annotated[types.CallToolResult, ConsumableItemsResult]
IntentControlToolResult = Annotated[types.CallToolResult, IntentControlResult]
PingToolResult = Annotated[types.CallToolResult, PingResult]


@asynccontextmanager
async def _stdio_server_skip_blank_lines(
    stdin: anyio.AsyncFile[str] | None = None,
    stdout: anyio.AsyncFile[str] | None = None,
):
    """Ignore blank input lines so manual terminal runs stay quiet."""
    if not stdin:
        stdin = anyio.wrap_file(TextIOWrapper(sys.stdin.buffer, encoding="utf-8", errors="replace"))
    if not stdout:
        stdout = anyio.wrap_file(TextIOWrapper(sys.stdout.buffer, encoding="utf-8"))

    read_stream: MemoryObjectReceiveStream[SessionMessage | Exception]
    read_stream_writer: MemoryObjectSendStream[SessionMessage | Exception]
    write_stream: MemoryObjectSendStream[SessionMessage]
    write_stream_reader: MemoryObjectReceiveStream[SessionMessage]

    read_stream_writer, read_stream = anyio.create_memory_object_stream(0)
    write_stream, write_stream_reader = anyio.create_memory_object_stream(0)

    async def stdin_reader():
        try:
            async with read_stream_writer:
                async for line in stdin:
                    if not line.strip():
                        continue
                    try:
                        message = types.JSONRPCMessage.model_validate_json(line)
                    except Exception as exc:
                        await read_stream_writer.send(exc)
                        continue
                    await read_stream_writer.send(SessionMessage(message))
        except anyio.ClosedResourceError:
            await anyio.lowlevel.checkpoint()

    async def stdout_writer():
        try:
            async with write_stream_reader:
                async for session_message in write_stream_reader:
                    payload = session_message.message.model_dump_json(by_alias=True, exclude_none=True)
                    await stdout.write(payload + "\n")
                    await stdout.flush()
        except anyio.ClosedResourceError:
            await anyio.lowlevel.checkpoint()

    async with anyio.create_task_group() as tg:
        tg.start_soon(stdin_reader)
        tg.start_soon(stdout_writer)
        yield read_stream, write_stream


fastmcp_server_module.stdio_server = _stdio_server_skip_blank_lines

logger.info(f"Logging to file: {log_file_path}")

mcp = FastMCP(SERVER_NAME)
mcp._mcp_server.version = SERVER_VERSION
_adapter: Optional[MijiaAdapter] = None


def get_adapter() -> Optional[MijiaAdapter]:
    global _adapter
    if _adapter is None:
        try:
            _adapter = MijiaAdapter()
            logger.info("Mijia adapter created successfully")
        except Exception as exc:
            logger.error(f"Failed to create Mijia adapter: {exc}")
    return _adapter


async def ensure_connected(adapter: MijiaAdapter) -> None:
    if not adapter.connected:
        connected = await adapter.connect()
        if not connected:
            raise RuntimeError("Failed to connect to Mijia cloud service")


async def get_known_room_names(adapter: MijiaAdapter) -> List[str]:
    homes = await adapter.get_homes()
    room_names: List[str] = []
    for home in homes:
        home_summary = normalize_home(home)
        room_names.extend([room["name"] for room in home_summary["rooms"] if room.get("name")])
    return room_names


async def resolve_home(adapter: MijiaAdapter, home_name: str = "", home_id: str = "") -> Dict[str, Any]:
    homes = await adapter.get_homes()
    normalized = [normalize_home(home) for home in homes]

    if home_id:
        for home in normalized:
            if home["home_id"] == str(home_id):
                return home
        raise RuntimeError(f"Home with id {home_id} not found")

    if home_name:
        exact = [home for home in normalized if str(home.get("name", "")).lower() == home_name.strip().lower()]
        if exact:
            if len(exact) > 1:
                raise RuntimeError(f"Multiple homes matched {home_name!r}")
            return exact[0]
        fuzzy = [home for home in normalized if home_name.strip().lower() in str(home.get("name", "")).lower()]
        if not fuzzy:
            raise RuntimeError(f"No home matched {home_name!r}")
        if len(fuzzy) > 1:
            raise RuntimeError(f"Multiple homes matched {home_name!r}")
        return fuzzy[0]

    raise RuntimeError("Either home_id or home_name is required")


async def list_normalized_devices(adapter: MijiaAdapter, refresh: bool = False) -> List[Dict[str, Any]]:
    devices = await adapter.list_device_infos(refresh=refresh)
    return [normalize_device(device) | {"raw": device} for device in devices]


async def resolve_device(
    adapter: MijiaAdapter,
    device_name: str = "",
    device_id: str = "",
    room: str = "",
    home: str = "",
    device_type: str = "",
    refresh: bool = False,
) -> Dict[str, Any]:
    if refresh:
        await adapter.list_device_infos(refresh=True)
    device = await adapter.resolve_single_device(
        device_name=device_name,
        device_id=device_id,
        room=room,
        home=home,
        device_type=device_type,
    )
    return normalize_device(device) | {"raw": device}


async def get_device_profile(adapter: MijiaAdapter, device_id: str) -> Dict[str, Any]:
    devices = await adapter.list_device_infos(refresh=False)
    device_info = next((device for device in devices if str(device.get("did")) == str(device_id)), {"did": device_id})
    normalized_device = normalize_device(device_info)
    properties = dedupe_properties(await adapter.get_device_properties(device_id))
    actions = dedupe_actions(await adapter.get_device_actions(device_id))
    capabilities = summarize_capabilities(properties, actions)
    capability_profile = build_device_capability_profile(device_info, properties, actions)
    mapping_report = build_capability_mapping_report(properties, actions, capability_profile)

    state: Dict[str, Any] = {}
    for control_name, target in capability_profile["controls"].items():
        if target.get("kind") == "property" and target.get("readable") and target.get("name"):
            try:
                state[control_name] = await adapter.get_property_value_by_name(device_id, target["name"])
            except Exception:
                continue

    if normalized_device.get("device_type") in READ_MOSTLY_DEVICE_TYPES:
        for prop in properties:
            prop_name = getattr(prop, "name", None)
            if not prop_name or prop_name in state:
                continue
            if not getattr(prop, "rw", None) or "r" in str(getattr(prop, "rw", "")).lower():
                try:
                    state[prop_name] = await adapter.get_property_value_by_name(device_id, prop_name)
                except Exception:
                    continue

    profile = {
        "capabilities": capabilities,
        "capability_profile": capability_profile,
        "mapping_report": mapping_report,
        "standard_capability_schema": build_standard_capability_schema(capability_profile),
        "profile_driven_schema": build_profile_driven_schema(properties, actions),
        "supported_operations": describe_supported_operations(capability_profile["supported_operations"]),
        "state": state,
        "state_summary": build_state_summary(state),
    }
    profile["device_resource"] = build_device_resource(normalized_device, profile)
    return profile


def summarize_device_profile(profile: Dict[str, Any]) -> Dict[str, Any]:
    capability_profile = profile["capability_profile"]
    summary_controls = []
    for capability_name, target in capability_profile.get("controls", {}).items():
        summary_controls.append(
            {
                "capability": capability_name,
                "kind": target.get("kind"),
                "name": target.get("name"),
                "readable": target.get("readable"),
                "writable": target.get("writable"),
            }
        )

    summary_supported_operations = [
        {
            "operation": item["operation"],
            "enabled": item["enabled"],
            "preferred_tool": item["preferred_tool"],
        }
        for item in profile.get("supported_operations", [])
        if item.get("enabled")
    ]

    mapping_report = profile.get("mapping_report", {})
    return {
        "primary_domain": capability_profile.get("primary_domain"),
        "device_domains": capability_profile.get("device_domains", []),
        "capability_families": capability_profile.get("capability_families", []),
        "controls": summary_controls,
        "supported_operations": summary_supported_operations,
        "state": profile.get("state", {}),
        "state_summary": build_state_summary(profile.get("state", {})),
        "mapping_summary": {
            "mapped_property_count": mapping_report.get("mapped_property_count", 0),
            "unmapped_property_count": mapping_report.get("unmapped_property_count", 0),
            "mapped_action_count": mapping_report.get("mapped_action_count", 0),
            "unmapped_action_count": mapping_report.get("unmapped_action_count", 0),
            "coverage": mapping_report.get("coverage", {}),
        },
        "profile_driven_controls": {
            "generic_operations": profile.get("profile_driven_schema", {}).get("generic_operations", {}),
            "writable_properties": [
                {
                    "name": item.get("name"),
                    "description": item.get("description"),
                    "type": item.get("type"),
                    "range": item.get("range"),
                    "value_list": item.get("value_list"),
                }
                for item in profile.get("profile_driven_schema", {}).get("writable_properties", [])
            ],
            "actions": [
                {
                    "name": item.get("name"),
                    "description": item.get("description"),
                }
                for item in profile.get("profile_driven_schema", {}).get("actions", [])
            ],
        },
        "device_resource": profile.get("device_resource", {}),
    }


def build_enabled_operations(profile: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [
        {
            "operation": item["operation"],
            "preferred_tool": item["preferred_tool"],
        }
        for item in profile.get("supported_operations", [])
        if item.get("enabled")
    ]


def build_device_status_payload(device: Dict[str, Any], profile: Dict[str, Any]) -> Dict[str, Any]:
    enabled_operations = build_enabled_operations(profile)
    state_summary = profile.get("state_summary", build_state_summary(profile.get("state", {})))
    return {
        "device": {k: v for k, v in device.items() if k != "raw"},
        "device_resource": profile.get("device_resource", {}),
        "state": profile.get("state", {}),
        "state_summary": state_summary,
        "supported_operations": enabled_operations,
        "assistant_summary": (
            f"{device.get('name')} 当前位于 {device.get('location', {}).get('label') or '未知位置'}，"
            f"在线状态为 {'在线' if device.get('online') else '离线'}。"
            f"当前摘要：{state_summary}"
        ),
        "quick_actions": [item["operation"] for item in enabled_operations[:5]],
        "next_steps": {
            "use_control_by_intent": bool(profile.get("device_resource", {}).get("usage")),
            "use_control_device": bool(profile.get("profile_driven_schema", {}).get("generic_operations")),
            "check_capabilities_with": "get_device_capabilities",
        },
    }


def build_home_overview(
    homes: List[Dict[str, Any]],
    devices: List[Dict[str, Any]],
    home_name: str = "",
    room: str = "",
) -> Dict[str, Any]:
    home_name_lower = home_name.strip().lower()
    room_lower = room.strip().lower()
    normalized_homes = [normalize_home(home) for home in homes]
    normalized_devices = [normalize_device_summary(device) for device in devices]

    if home_name_lower:
        normalized_homes = [home for home in normalized_homes if home_name_lower in str(home.get("name", "")).lower()]
        normalized_devices = [device for device in normalized_devices if home_name_lower in str(device.get("home_name", "")).lower()]

    overview_homes = []
    for home in normalized_homes:
        rooms = []
        for room_info in home.get("rooms", []):
            room_devices = [
                device for device in normalized_devices
                if str(device.get("home_id", home.get("home_id"))) == str(home.get("home_id"))
                and str(device.get("room_name", "") or "") == str(room_info.get("name", "") or "")
            ]
            if room_lower and room_lower not in str(room_info.get("name", "")).lower():
                continue
            rooms.append(
                {
                    "room_id": room_info.get("room_id"),
                    "name": room_info.get("name"),
                    "device_count": len(room_devices),
                    "devices": room_devices[:12],
                }
            )

        home_devices = [
            device for device in normalized_devices
            if str(device.get("home_name", "") or "") == str(home.get("name", "") or "")
        ]
        overview_homes.append(
            {
                "home_id": home.get("home_id"),
                "name": home.get("name"),
                "room_count": len(rooms),
                "device_count": len(home_devices),
                "rooms": rooms,
            }
        )

    return {
        "homes": overview_homes,
        "home_count": len(overview_homes),
        "device_count": len(normalized_devices),
        "assistant_summary": (
            f"已整理 {len(overview_homes)} 个家庭、{len(normalized_devices)} 台设备的房间视图。"
            "优先查看 rooms 和 devices 字段即可。"
        ),
        "next_steps": {
            "refresh_with": "refresh_devices",
            "inspect_device_with": "get_device_status",
            "control_with": "control_by_intent",
        },
    }


def build_home_directory(homes: List[Dict[str, Any]], devices: List[Dict[str, Any]]) -> Dict[str, Any]:
    normalized_homes = [normalize_home(home) for home in homes]
    normalized_devices = [normalize_device_summary(device) for device in devices]
    home_rows = []

    for home in normalized_homes:
        rooms = []
        for room_info in home.get("rooms", []):
            room_devices = [
                device for device in normalized_devices
                if str(device.get("home_id", "")) == str(home.get("home_id", ""))
                and str(device.get("room_name", "") or "") == str(room_info.get("name", "") or "")
            ]
            rooms.append(
                {
                    "room_id": room_info.get("room_id"),
                    "name": room_info.get("name"),
                    "device_count": len(room_devices),
                }
            )

        home_devices = [
            device for device in normalized_devices
            if str(device.get("home_id", "")) == str(home.get("home_id", ""))
        ]
        home_rows.append(
            {
                "home_id": home.get("home_id"),
                "name": home.get("name"),
                "room_count": len(rooms),
                "device_count": len(home_devices),
                "rooms": rooms,
            }
        )

    return {
        "homes": home_rows,
        "home_count": len(home_rows),
        "assistant_summary": (
            f"已整理 {len(home_rows)} 个家庭的房间目录。"
            "如果客户端暂时没有走到 get_home_overview，这个结果也足够先做房间级浏览和筛选。"
        ),
        "next_steps": {
            "overview_with": "get_home_overview",
            "list_devices_with": "list_devices",
            "inspect_device_with": "get_device_status",
        },
    }


def build_tool_catalog() -> Dict[str, Any]:
    everyday_tools = [
        {
            "name": "refresh_devices",
            "category": "service",
            "purpose": "同步米家云端设备、家庭和房间映射，适合首轮使用前执行一次",
        },
        {
            "name": "get_home_overview",
            "category": "home",
            "purpose": "按家庭和房间查看设备总览，适合先理解家里的结构",
        },
        {
            "name": "get_device_status",
            "category": "device",
            "purpose": "快速查看单个设备当前状态、可用操作和下一步建议",
        },
        {
            "name": "control_by_intent",
            "category": "device",
            "purpose": "优先用自然语言式请求完成常见控制，例如打开灯或调整亮度",
        },
        {
            "name": "list_scenes",
            "category": "scene",
            "purpose": "查看可执行的场景列表",
        },
        {
            "name": "execute_scene",
            "category": "scene",
            "purpose": "执行一个家庭场景，例如回家模式或睡眠模式",
        },
    ]

    advanced_tools = [
        {
            "name": "get_service_status",
            "category": "service",
            "purpose": "查看服务连接、认证文件和运行状态",
        },
        {
            "name": "prepare_login",
            "category": "service",
            "purpose": "主动准备二维码登录，必要时重开浏览器页或触发重新认证",
        },
        {
            "name": "reconnect_service",
            "category": "service",
            "purpose": "重连米家服务，必要时强制重新认证",
        },
        {
            "name": "clear_saved_login",
            "category": "service",
            "purpose": "清除已保存登录信息，下一次连接会重新走二维码登录",
        },
        {
            "name": "list_homes",
            "category": "home",
            "purpose": "查看家庭和房间清单，适合更精细的客户端路由",
        },
        {
            "name": "list_devices",
            "category": "device",
            "purpose": "按房间、家庭、设备类型或在线状态筛选设备列表",
        },
        {
            "name": "get_device",
            "category": "device",
            "purpose": "查看单个设备的摘要、能力和 profile 驱动信息",
        },
        {
            "name": "get_device_capabilities",
            "category": "device",
            "purpose": "查看标准能力 schema 和 profile 驱动控制项，适合稳定路由",
        },
        {
            "name": "control_device",
            "category": "device",
            "purpose": "统一控制入口，适合结构化调用和 profile fallback",
        },
        {
            "name": "turn_on_device",
            "category": "device",
            "purpose": "显式打开支持开关的设备",
        },
        {
            "name": "turn_off_device",
            "category": "device",
            "purpose": "显式关闭支持开关的设备",
        },
        {
            "name": "set_brightness",
            "category": "device",
            "purpose": "设置支持亮度控制设备的亮度",
        },
        {
            "name": "set_color_temperature",
            "category": "device",
            "purpose": "设置支持色温控制设备的色温",
        },
        {
            "name": "set_target_temperature",
            "category": "device",
            "purpose": "设置支持目标温度控制设备的温度",
        },
        {
            "name": "set_hvac_mode",
            "category": "device",
            "purpose": "设置支持模式切换设备的模式",
        },
        {
            "name": "set_fan_speed",
            "category": "device",
            "purpose": "设置支持风速控制设备的风速",
        },
        {
            "name": "set_cover_position",
            "category": "device",
            "purpose": "设置支持位置控制设备的开合位置",
        },
        {
            "name": "get_consumable_items",
            "category": "home",
            "purpose": "查看家庭中的耗材条目",
        },
        {
            "name": "ping",
            "category": "service",
            "purpose": "检测 MCP 服务是否仍可连通",
        },
    ]

    recommended_workflow = [
        {
            "step": 1,
            "tool": "refresh_devices",
            "goal": "先同步设备、家庭和房间映射",
        },
        {
            "step": 2,
            "tool": "get_home_overview",
            "goal": "先理解家庭和房间结构",
        },
        {
            "step": 3,
            "tool": "get_device_status",
            "goal": "查看某个设备当前状态和推荐操作",
        },
        {
            "step": 4,
            "tool": "control_by_intent",
            "goal": "优先走自然语言式控制",
        },
        {
            "step": 5,
            "tool": "control_device",
            "goal": "需要更稳定或更底层时再走结构化控制",
        },
    ]

    return {
        "everyday_tools": everyday_tools,
        "advanced_tools": advanced_tools,
        "recommended_workflow": recommended_workflow,
        "assistant_summary": (
            "优先使用 everyday_tools 可以明显降低首次接入和日常控制的复杂度；"
            "advanced_tools 更适合调试、精细路由或构建更强的客户端。"
        ),
    }


def build_service_status_payload(adapter: Optional[MijiaAdapter]) -> Dict[str, Any]:
    if not adapter:
        return {
            "service": {
                "name": SERVER_NAME,
                "version": SERVER_VERSION,
                "connected": False,
                "has_saved_login": False,
                "auth_file": None,
                "log_file": str(log_file_path),
                "qr": None,
                "device_count": 0,
            },
            "assistant_summary": "服务尚未初始化，先检查服务启动状态。",
            "next_steps": {
                "prepare_login_with": "prepare_login",
                "status_with": "get_service_status",
            },
        }

    qr_status = adapter.get_qr_status()
    connected = adapter.connected
    has_saved_login = adapter.has_valid_auth_data()
    should_scan_qr = bool(not connected and qr_status.get("enabled") and (not has_saved_login or qr_status.get("page_exists") or qr_status.get("image_exists")))

    if connected:
        assistant_summary = "服务已连接米家云，可以直接刷新设备或开始控制。"
    elif should_scan_qr:
        assistant_summary = "服务当前未连接，建议先扫码完成登录；二维码页和图片路径已在 service.qr 中提供。"
    elif has_saved_login:
        assistant_summary = "服务当前未连接，但本地存在已保存登录，可尝试重连。"
    else:
        assistant_summary = "服务当前未连接，也没有可用的已保存登录，建议先准备二维码登录。"

    return {
        "service": {
            "name": SERVER_NAME,
            "version": SERVER_VERSION,
            "connected": connected,
            "has_saved_login": has_saved_login,
            "auth_file": str(adapter.get_auth_file_path()),
            "log_file": str(log_file_path),
            "qr": qr_status,
            "device_count": adapter.device_count,
        },
        "assistant_summary": assistant_summary,
        "next_steps": {
            "should_scan_qr": should_scan_qr,
            "prepare_login_with": "prepare_login",
            "reconnect_with": "reconnect_service",
            "refresh_devices_with": "refresh_devices" if connected else None,
        },
    }


def build_control_assistant_summary(device_name: str, operation: str, outcome: Dict[str, Any]) -> str:
    after_summary = outcome.get("after_summary", {})
    if operation == "turn_on":
        return f"已请求打开 {device_name}。当前状态摘要：{after_summary}"
    if operation == "turn_off":
        return f"已请求关闭 {device_name}。当前状态摘要：{after_summary}"
    if operation == "toggle":
        return f"已请求切换 {device_name}。当前状态摘要：{after_summary}"
    return f"已对 {device_name} 执行 {operation}。当前状态摘要：{after_summary}"


def build_state_summary(state: Dict[str, Any]) -> Dict[str, Any]:
    power = state.get("power")
    return {
        "power": power,
        "power_status": "on" if power is True else "off" if power is False else "unknown",
        "brightness": state.get("brightness"),
        "color_temperature": state.get("color_temperature"),
        "mode": state.get("mode"),
        "target_temperature": state.get("target_temperature"),
        "fan_speed": state.get("fan_speed"),
        "cover_position": state.get("cover_position"),
        "temperature": state.get("temperature"),
        "humidity": state.get("relative-humidity"),
        "battery_level": state.get("battery-level"),
    }


def summarize_control_outcome(operation: str, before_state: Dict[str, Any], after_state: Dict[str, Any]) -> Dict[str, Any]:
    changed_keys = sorted(
        key for key in set(before_state) | set(after_state)
        if before_state.get(key) != after_state.get(key)
    )
    power_changed = before_state.get("power") != after_state.get("power")
    expected_power = None
    if operation == "turn_on":
        expected_power = True
    elif operation == "turn_off":
        expected_power = False

    return {
        "changed": bool(changed_keys),
        "changed_keys": changed_keys,
        "power_changed": power_changed,
        "expected_power": expected_power,
        "power_matches_expectation": expected_power is None or after_state.get("power") == expected_power,
        "before_summary": build_state_summary(before_state),
        "after_summary": build_state_summary(after_state),
    }


def find_profile_control_match(query: str, profile: Dict[str, Any]) -> Dict[str, Any] | None:
    lowered_query = query.strip().lower()
    if not lowered_query:
        return None

    profile_driven = profile.get("profile_driven_schema", {})
    writable_properties = profile_driven.get("writable_properties", [])
    actions = profile_driven.get("actions", [])

    def score_match(item: Dict[str, Any]) -> int:
        score = 0
        for term in item.get("matching_terms", []):
            normalized_term = str(term).strip().lower()
            if not normalized_term:
                continue
            if normalized_term in lowered_query:
                score = max(score, len(normalized_term))
        return score

    best_property = None
    best_property_score = 0
    for item in writable_properties:
        score = score_match(item)
        if score > best_property_score:
            best_property = item
            best_property_score = score

    best_action = None
    best_action_score = 0
    for item in actions:
        score = score_match(item)
        if score > best_action_score:
            best_action = item
            best_action_score = score

    if best_property_score <= 0 and best_action_score <= 0:
        return None

    if best_property_score >= best_action_score and best_property:
        return {
            "kind": "property",
            "name": best_property.get("name"),
            "description": best_property.get("description"),
            "type": best_property.get("type"),
            "range": best_property.get("range"),
            "value_list": best_property.get("value_list"),
        }

    if best_action:
        return {
            "kind": "action",
            "name": best_action.get("name"),
            "description": best_action.get("description"),
        }
    return None


async def control_device_with_profile_fallback(
    adapter: MijiaAdapter,
    query: str,
    device_name: str,
    room: str = "",
    home: str = "",
    prefer_device_type: str = "",
    parsed_intent: Dict[str, Any] | None = None,
) -> ControlToolResult:
    device = await resolve_device(
        adapter,
        device_name=device_name,
        room=room,
        home=home,
        device_type=prefer_device_type,
    )
    profile = await get_device_profile(adapter, device["device_id"])
    match = find_profile_control_match(query, profile)
    if not match:
        return build_result(
            False,
            f"Could not match a profile-driven control for {device['name']}",
            device={k: v for k, v in device.items() if k != "raw"},
            device_resource=profile.get("device_resource"),
            profile_driven_controls=profile.get("profile_driven_schema", {}),
            parsed_intent=parsed_intent or {},
        )

    if match["kind"] == "property":
        value = parsed_intent.get("value") if parsed_intent else None
        if value is None:
            return build_result(
                False,
                f"Matched property {match['name']} on {device['name']} but no value was provided",
                device={k: v for k, v in device.items() if k != "raw"},
                matched_control=match,
                device_resource=profile.get("device_resource"),
                parsed_intent=parsed_intent or {},
            )
        capability_name = None
        for item in profile.get("profile_driven_schema", {}).get("writable_properties", []):
            if item.get("name") == match["name"]:
                if item.get("value_list"):
                    capability_name = "mode"
                break
        if capability_name:
            resolved_target = {
                "name": match["name"],
                "value_list": next(
                    (
                        item.get("value_list")
                        for item in profile.get("profile_driven_schema", {}).get("writable_properties", [])
                        if item.get("name") == match["name"]
                    ),
                    None,
                ),
                "range": next(
                    (
                        item.get("range")
                        for item in profile.get("profile_driven_schema", {}).get("writable_properties", [])
                        if item.get("name") == match["name"]
                    ),
                    None,
                ),
            }
            value = coerce_value_for_target(capability_name, resolved_target, value)
        return await control_device(
            "set_property",
            device_id=device["device_id"],
            value=value,
            property_name=match["name"],
        )

    return await control_device(
        "run_action",
        device_id=device["device_id"],
        value=[],
        action_name=match["name"],
    )


async def list_normalized_scenes(adapter: MijiaAdapter, home_name: str = "", home_id: str = "") -> List[Dict[str, Any]]:
    if home_id or home_name:
        home = await resolve_home(adapter, home_name=home_name, home_id=home_id)
        scenes = await adapter.get_scenes_list(home["home_id"])
        return [normalize_scene(scene, home["name"]) for scene in scenes]

    homes = await adapter.get_homes()
    all_scenes: List[Dict[str, Any]] = []
    for home in homes:
        home_summary = normalize_home(home)
        scenes = await adapter.get_scenes_list(home_summary["home_id"])
        all_scenes.extend(normalize_scene(scene, home_summary["name"]) for scene in scenes)
    return all_scenes


async def resolve_scene(adapter: MijiaAdapter, scene_name: str = "", scene_id: str = "", home_name: str = "", home_id: str = "") -> Dict[str, Any]:
    scenes = await list_normalized_scenes(adapter, home_name=home_name, home_id=home_id)
    if scene_id:
        for scene in scenes:
            if scene["scene_id"] == str(scene_id):
                return scene
        raise RuntimeError(f"Scene with id {scene_id} not found")

    if scene_name:
        exact = [scene for scene in scenes if str(scene.get("name", "")).lower() == scene_name.strip().lower()]
        if exact:
            if len(exact) > 1:
                raise RuntimeError(f"Multiple scenes matched {scene_name!r}")
            return exact[0]
        fuzzy = [scene for scene in scenes if scene_name.strip().lower() in str(scene.get("name", "")).lower()]
        if not fuzzy:
            raise RuntimeError(f"No scene matched {scene_name!r}")
        if len(fuzzy) > 1:
            raise RuntimeError(f"Multiple scenes matched {scene_name!r}")
        return fuzzy[0]

    raise RuntimeError("Either scene_id or scene_name is required")


async def execute_operation(
    adapter: MijiaAdapter,
    device: Dict[str, Any],
    device_id: str,
    operation: str,
    value: Any = None,
    property_name: str = "",
    action_name: str = "",
) -> Dict[str, Any]:
    properties = dedupe_properties(await adapter.get_device_properties(device_id))
    actions = dedupe_actions(await adapter.get_device_actions(device_id))
    capability_profile = build_device_capability_profile(device, properties, actions)
    controls = capability_profile["controls"]
    supported_operations = capability_profile["supported_operations"]

    if operation in supported_operations and not supported_operations[operation]:
        raise RuntimeError(
            f"This {capability_profile['primary_domain']} device does not support {operation}. "
            f"Supported operations: {', '.join(name for name, enabled in supported_operations.items() if enabled) or 'none'}"
        )

    if operation == "turn_on":
        target = controls.get("power")
        if not target or not target.get("writable"):
            raise RuntimeError("This device does not expose a writable power capability")
        await adapter.set_property_value_by_name(device_id, target["name"], True)
        return {"operation": operation, "target": target, "value": True, "primary_domain": capability_profile["primary_domain"]}

    if operation == "turn_off":
        target = controls.get("power")
        if not target or not target.get("writable"):
            raise RuntimeError("This device does not expose a writable power capability")
        await adapter.set_property_value_by_name(device_id, target["name"], False)
        return {"operation": operation, "target": target, "value": False, "primary_domain": capability_profile["primary_domain"]}

    if operation == "toggle":
        action_target = controls.get("toggle")
        if action_target:
            await adapter.call_action_by_name(device_id, action_target["name"], [])
            return {"operation": operation, "target": action_target, "primary_domain": capability_profile["primary_domain"]}
        power_target = controls.get("power")
        if power_target:
            current_value = await adapter.get_property_value_by_name(device_id, power_target["name"])
            next_value = not bool(current_value)
            await adapter.set_property_value_by_name(device_id, power_target["name"], next_value)
            return {"operation": operation, "target": power_target, "value": next_value, "primary_domain": capability_profile["primary_domain"]}
        raise RuntimeError("This device does not support toggle control")

    capability_name = OPERATION_CAPABILITY_MAP.get(operation)
    if capability_name:
        capability_definition = get_capability_definition(capability_name)
        if capability_definition["kind"] == "property" and operation.startswith("set_"):
            target = controls.get(capability_name)
            if not target or not target.get("writable"):
                raise RuntimeError(f"This device does not support {capability_definition['label'].lower()} control")
            resolved_value = coerce_value_for_target(capability_name, target, value)
            if capability_definition.get("value_type") == "integer":
                resolved_value = int(resolved_value)
            await adapter.set_property_value_by_name(device_id, target["name"], resolved_value)
            return {
                "operation": operation,
                "capability": capability_name,
                "target": target,
                "value": resolved_value,
                "capability_definition": build_standard_capability_definition(capability_name, target),
                "primary_domain": capability_profile["primary_domain"],
            }

    if operation == "set_property":
        if not property_name:
            raise RuntimeError("property_name is required for set_property")
        await adapter.set_property_value_by_name(device_id, property_name, value)
        return {"operation": operation, "target": property_name, "value": value}

    if operation == "run_action":
        if not action_name:
            raise RuntimeError("action_name is required for run_action")
        await adapter.call_action_by_name(device_id, action_name, value or [])
        return {"operation": operation, "target": action_name, "value": value or []}

    raise RuntimeError(f"Unsupported operation: {operation}")


@mcp.resource("mijia://service")
async def service_resource() -> str:
    adapter = get_adapter()
    payload = build_service_status_payload(adapter)
    return build_resource_result(
        True,
        "Service metadata",
        **payload,
    )


@mcp.resource("mijia://homes")
async def homes_resource() -> str:
    adapter = get_adapter()
    if not adapter:
        return build_resource_result(False, "Adapter not initialized")
    try:
        await ensure_connected(adapter)
        homes = [normalize_home(home) for home in await adapter.get_homes()]
        return build_resource_result(True, f"Loaded {len(homes)} homes", homes=homes, count=len(homes))
    except Exception as exc:
        logger.error(f"Failed to load homes resource: {exc}")
        return build_resource_result(False, str(exc), error={"details": str(exc)})


@mcp.resource("mijia://devices")
async def devices_resource() -> str:
    adapter = get_adapter()
    if not adapter:
        return build_resource_result(False, "Adapter not initialized")
    try:
        await ensure_connected(adapter)
        devices = await list_normalized_devices(adapter, refresh=False)
        return build_resource_result(
            True,
            f"Loaded {len(devices)} devices",
            devices=[{k: v for k, v in device.items() if k != "raw"} for device in devices],
            count=len(devices),
        )
    except Exception as exc:
        logger.error(f"Failed to load devices resource: {exc}")
        return build_resource_result(False, str(exc), error={"details": str(exc)})


@mcp.resource("mijia://scenes")
async def scenes_resource() -> str:
    adapter = get_adapter()
    if not adapter:
        return build_resource_result(False, "Adapter not initialized")
    try:
        await ensure_connected(adapter)
        scenes = await list_normalized_scenes(adapter)
        return build_resource_result(True, f"Loaded {len(scenes)} scenes", scenes=scenes, count=len(scenes))
    except Exception as exc:
        logger.error(f"Failed to load scenes resource: {exc}")
        return build_resource_result(False, str(exc), error={"details": str(exc)})


@mcp.resource("mijia://capabilities")
async def capabilities_resource() -> str:
    return build_resource_result(True, "Standard capability catalog", capabilities={
        "capabilities": get_capability_catalog(),
        "intents": get_intent_catalog(),
    })


@mcp.resource("mijia://tooling")
async def tooling_resource() -> str:
    return build_resource_result(True, "Tool catalog and recommended workflow", tooling=build_tool_catalog())


@mcp.tool(name="get_service_status")
async def get_service_status() -> ServiceStatusToolResult:
    """Return service status, authentication status, and local file locations."""
    adapter = get_adapter()
    if not adapter:
        return build_result(False, "Adapter not initialized")

    return build_result(
        True,
        "Service status loaded",
        **build_service_status_payload(adapter),
    )


@mcp.tool(name="reconnect_service")
async def reconnect_service(force_reauth: bool = False) -> ServiceStatusToolResult:
    """Reconnect to Mijia cloud, optionally clearing saved login first."""
    adapter = get_adapter()
    if not adapter:
        return build_result(False, "Adapter not initialized")

    try:
        if force_reauth:
            adapter.clear_auth_data()
        await adapter.disconnect()
        connected = await adapter.connect()
        return build_result(
            connected,
            "Reconnected service" if connected else "Reconnect failed",
            action="reconnect",
            **build_service_status_payload(adapter),
        )
    except Exception as exc:
        logger.error(f"Failed to reconnect service: {exc}")
        return build_error_result(exc)


@mcp.tool(name="prepare_login")
async def prepare_login(force_reauth: bool = False, reopen_qr: bool = True) -> ServiceStatusToolResult:
    """Prepare QR login artifacts and optionally force a fresh QR login flow."""
    adapter = get_adapter()
    if not adapter:
        return build_result(False, "Adapter not initialized")

    try:
        action = "status_only"
        if force_reauth:
            adapter.clear_auth_data()
            await adapter.disconnect()
            connected = await adapter.connect()
            action = "force_reauth"
            if reopen_qr:
                adapter.open_qr_artifacts()
            return build_result(
                connected,
                "Forced QR login flow prepared" if connected else "QR login flow started but connection is not ready yet",
                action=action,
                **build_service_status_payload(adapter),
            )

        qr_status = adapter.get_qr_status()
        reopened = False
        if reopen_qr and (qr_status.get("page_exists") or qr_status.get("image_exists")):
            reopened = adapter.open_qr_artifacts()
            action = "reopen_qr" if reopened else "status_only"

        return build_result(
            True,
            "Login artifacts are ready" if reopened else "Loaded current login status",
            action=action,
            **build_service_status_payload(adapter),
        )
    except Exception as exc:
        logger.error(f"Failed to prepare login: {exc}")
        return build_error_result(exc)


@mcp.tool(name="clear_saved_login")
async def clear_saved_login() -> ServiceStatusToolResult:
    """Clear saved login credentials so the next connection triggers QR login."""
    adapter = get_adapter()
    if not adapter:
        return build_result(False, "Adapter not initialized")

    try:
        cleared = adapter.clear_auth_data()
        await adapter.disconnect()
        return build_result(cleared, "Cleared saved login" if cleared else "Failed to clear saved login")
    except Exception as exc:
        logger.error(f"Failed to clear saved login: {exc}")
        return build_error_result(exc)


@mcp.tool(name="list_homes")
async def list_homes(refresh: bool = False) -> HomeListToolResult:
    """List all homes and rooms in a user-friendly structure."""
    adapter = get_adapter()
    if not adapter:
        return build_result(False, "Adapter not initialized")

    try:
        await ensure_connected(adapter)
        homes = await adapter.get_homes()
        devices = await adapter.list_device_infos(refresh=refresh or not adapter.device_count)
        directory = build_home_directory(homes, devices)
        return build_result(
            True,
            f"Loaded {directory['home_count']} homes",
            **directory,
            response_mode="summary",
            fallback_for="get_home_overview",
        )
    except Exception as exc:
        logger.error(f"Failed to list homes: {exc}")
        return build_error_result(exc)


@mcp.tool(name="refresh_devices")
async def refresh_devices() -> HomeListToolResult:
    """Refresh homes, devices, and room mappings from Mijia cloud."""
    adapter = get_adapter()
    if not adapter:
        return build_result(False, "Adapter not initialized")

    try:
        await ensure_connected(adapter)
        homes = await adapter.get_homes()
        devices = await adapter.list_device_infos(refresh=True)
        return build_result(
            True,
            f"Refreshed {len(devices)} devices across {len(homes)} homes",
            homes=[normalize_home(home) for home in homes],
            home_count=len(homes),
            device_count=len(devices),
            refreshed=True,
        )
    except Exception as exc:
        logger.error(f"Failed to refresh devices: {exc}")
        return build_error_result(exc)


@mcp.tool(name="get_tool_catalog")
async def get_tool_catalog() -> ToolCatalogToolResult:
    """Return the recommended everyday tools, advanced tools, and workflow."""
    catalog = build_tool_catalog()
    return build_result(
        True,
        "Loaded tool catalog",
        **catalog,
    )


@mcp.tool(name="get_home_overview")
async def get_home_overview(home_name: str = "", room: str = "", refresh: bool = False) -> HomeListToolResult:
    """Return a room-first overview of homes and devices for everyday browsing."""
    adapter = get_adapter()
    if not adapter:
        return build_result(False, "Adapter not initialized")

    try:
        await ensure_connected(adapter)
        homes = await adapter.get_homes()
        devices = await adapter.list_device_infos(refresh=refresh or not adapter.device_count)
        overview = build_home_overview(homes, devices, home_name=home_name, room=room)
        return build_result(
            True,
            f"Loaded overview for {overview['home_count']} homes",
            **overview,
            response_mode="summary",
        )
    except Exception as exc:
        logger.error(f"Failed to get home overview: {exc}")
        return build_error_result(exc)


@mcp.tool(name="list_devices")
async def list_devices(
    query: str = "",
    room: str = "",
    home: str = "",
    device_type: str = "",
    online_only: bool = False,
    refresh: bool = False,
    verbose: bool = False,
) -> DeviceListToolResult:
    """List devices by friendly filters like name, room, home, or model."""
    adapter = get_adapter()
    if not adapter:
        return build_result(False, "Adapter not initialized")

    try:
        await ensure_connected(adapter)
        if refresh:
            await adapter.list_device_infos(refresh=True)
        devices = await adapter.resolve_devices(
            query=query,
            room=room,
            home=home,
            device_type=device_type,
            online_only=online_only,
        )
        normalized = [normalize_device(device) if verbose else normalize_device_summary(device) for device in devices]
        return build_result(
            True,
            f"Found {len(normalized)} devices",
            devices=normalized,
            count=len(normalized),
            response_mode="full" if verbose else "summary",
        )
    except Exception as exc:
        logger.error(f"Failed to list devices: {exc}")
        return build_error_result(exc)


@mcp.tool(name="get_device")
async def get_device(
    device_name: str = "",
    device_id: str = "",
    room: str = "",
    home: str = "",
    device_type: str = "",
    verbose: bool = False,
    refresh: bool = False,
) -> DeviceToolResult:
    """Resolve one device and return its summary, capabilities, and common state."""
    adapter = get_adapter()
    if not adapter:
        return build_result(False, "Adapter not initialized")

    try:
        await ensure_connected(adapter)
        device = await resolve_device(
            adapter,
            device_name=device_name,
            device_id=device_id,
            room=room,
            home=home,
            device_type=device_type,
            refresh=refresh,
        )
        profile = await get_device_profile(adapter, device["device_id"])
        return build_result(
            True,
            f"Resolved device {device['name']}",
            device={k: v for k, v in device.items() if k != "raw"},
            profile=profile if verbose else summarize_device_profile(profile),
            response_mode="full" if verbose else "summary",
        )
    except Exception as exc:
        logger.error(f"Failed to get device: {exc}")
        return build_error_result(exc)


@mcp.tool(name="get_device_status")
async def get_device_status(
    device_name: str = "",
    device_id: str = "",
    room: str = "",
    home: str = "",
    device_type: str = "",
    refresh: bool = True,
) -> DeviceStatusToolResult:
    """Return the current state and recommended next actions for one device."""
    adapter = get_adapter()
    if not adapter:
        return build_result(False, "Adapter not initialized")

    try:
        await ensure_connected(adapter)
        device = await resolve_device(
            adapter,
            device_name=device_name,
            device_id=device_id,
            room=room,
            home=home,
            device_type=device_type,
            refresh=refresh,
        )
        profile = await get_device_profile(adapter, device["device_id"])
        return build_result(
            True,
            f"Loaded status for {device['name']}",
            **build_device_status_payload(device, profile),
            response_mode="summary",
        )
    except Exception as exc:
        logger.error(f"Failed to get device status: {exc}")
        return build_error_result(exc)


@mcp.tool(name="get_device_capabilities")
async def get_device_capabilities(
    device_name: str = "",
    device_id: str = "",
    room: str = "",
    home: str = "",
    device_type: str = "",
    verbose: bool = False,
    refresh: bool = False,
) -> DeviceCapabilitiesToolResult:
    """Resolve one device and return its standard capability schema for stable client-side routing."""
    adapter = get_adapter()
    if not adapter:
        return build_result(False, "Adapter not initialized")

    try:
        await ensure_connected(adapter)
        device = await resolve_device(
            adapter,
            device_name=device_name,
            device_id=device_id,
            room=room,
            home=home,
            device_type=device_type,
            refresh=refresh,
        )
        profile = await get_device_profile(adapter, device["device_id"])
        if verbose:
            return build_result(
                True,
                f"Loaded capability schema for {device['name']}",
                device={k: v for k, v in device.items() if k != "raw"},
                primary_domain=profile["capability_profile"]["primary_domain"],
                device_domains=profile["capability_profile"]["device_domains"],
                capability_families=profile["capability_profile"]["capability_families"],
                capability_schema=profile["standard_capability_schema"],
                capability_catalog={
                    "capabilities": get_capability_catalog(),
                    "intents": get_intent_catalog(),
                },
                mapping_report=profile["mapping_report"],
                profile_driven_schema=profile["profile_driven_schema"],
                device_resource=profile["device_resource"],
                supported_operations=profile["supported_operations"],
                state=profile["state"],
                response_mode="full",
            )
        return build_result(
            True,
            f"Loaded capability schema for {device['name']}",
            device={k: v for k, v in device.items() if k != "raw"},
            primary_domain=profile["capability_profile"]["primary_domain"],
            device_domains=profile["capability_profile"]["device_domains"],
            capability_families=profile["capability_profile"]["capability_families"],
            capability_schema=profile["standard_capability_schema"],
            profile_driven_schema=profile["profile_driven_schema"],
            device_resource=profile["device_resource"],
            supported_operations=[
                {
                    "operation": item["operation"],
                    "enabled": item["enabled"],
                    "preferred_tool": item["preferred_tool"],
                }
                for item in profile["supported_operations"]
                if item.get("enabled")
            ],
            state_summary=build_state_summary(profile["state"]),
            mapping_summary={
                "mapped_property_count": profile["mapping_report"]["mapped_property_count"],
                "unmapped_property_count": profile["mapping_report"]["unmapped_property_count"],
                "mapped_action_count": profile["mapping_report"]["mapped_action_count"],
                "unmapped_action_count": profile["mapping_report"]["unmapped_action_count"],
                "coverage": profile["mapping_report"]["coverage"],
            },
            response_mode="summary",
        )
    except Exception as exc:
        logger.error(f"Failed to get device capabilities: {exc}")
        return build_error_result(exc)


@mcp.tool(name="control_device")
async def control_device(
    operation: str,
    device_name: str = "",
    device_id: str = "",
    room: str = "",
    home: str = "",
    value: Any = None,
    property_name: str = "",
    action_name: str = "",
    refresh: bool = False,
) -> ControlToolResult:
    """Control a device through capability operations like turn_on, set_brightness, set_target_temperature, or run_action."""
    adapter = get_adapter()
    if not adapter:
        return build_result(False, "Adapter not initialized")

    try:
        await ensure_connected(adapter)
        device = await resolve_device(
            adapter,
            device_name=device_name,
            device_id=device_id,
            room=room,
            home=home,
            refresh=refresh,
        )
        before_profile = await get_device_profile(adapter, device["device_id"])
        execution = await execute_operation(
            adapter,
            device["raw"],
            device["device_id"],
            operation=operation,
            value=value,
            property_name=property_name,
            action_name=action_name,
        )
        after_profile = await get_device_profile(adapter, device["device_id"])
        outcome = summarize_control_outcome(operation, before_profile["state"], after_profile["state"])
        return build_result(
            True,
            f"Executed {operation} on {device['name']}",
            device={k: v for k, v in device.items() if k != "raw"},
            execution=execution,
            previous_state=before_profile["state"],
            current_state=after_profile["state"],
            state=after_profile["state"],
            outcome=outcome,
            assistant_summary=build_control_assistant_summary(device["name"], operation, outcome),
        )
    except Exception as exc:
        logger.error(f"Failed to control device: {exc}")
        return build_error_result(exc)


@mcp.tool(name="turn_on_device")
async def turn_on_device(device_name: str = "", device_id: str = "", room: str = "", home: str = "") -> ControlToolResult:
    """Turn on a device."""
    return await control_device("turn_on", device_name=device_name, device_id=device_id, room=room, home=home, refresh=True)


@mcp.tool(name="turn_off_device")
async def turn_off_device(device_name: str = "", device_id: str = "", room: str = "", home: str = "") -> ControlToolResult:
    """Turn off a device."""
    return await control_device("turn_off", device_name=device_name, device_id=device_id, room=room, home=home, refresh=True)


@mcp.tool(name="set_brightness")
async def set_brightness(device_name: str = "", device_id: str = "", room: str = "", home: str = "", value: int = 50) -> ControlToolResult:
    """Set device brightness."""
    return await control_device("set_brightness", device_name=device_name, device_id=device_id, room=room, home=home, value=value, refresh=True)


@mcp.tool(name="set_color_temperature")
async def set_color_temperature(device_name: str = "", device_id: str = "", room: str = "", home: str = "", value: int = 4000) -> ControlToolResult:
    """Set device color temperature."""
    return await control_device("set_color_temperature", device_name=device_name, device_id=device_id, room=room, home=home, value=value, refresh=True)


@mcp.tool(name="set_target_temperature")
async def set_target_temperature(device_name: str = "", device_id: str = "", room: str = "", home: str = "", value: int = 26) -> ControlToolResult:
    """Set target temperature on any target-temperature-capable device."""
    return await control_device("set_target_temperature", device_name=device_name, device_id=device_id, room=room, home=home, value=value, refresh=True)


@mcp.tool(name="set_hvac_mode")
async def set_hvac_mode(device_name: str = "", device_id: str = "", room: str = "", home: str = "", value: Any = "") -> ControlToolResult:
    """Set mode on a mode-capable device such as an air conditioner, fan, or purifier."""
    return await control_device("set_hvac_mode", device_name=device_name, device_id=device_id, room=room, home=home, value=value, refresh=True)


@mcp.tool(name="set_fan_speed")
async def set_fan_speed(device_name: str = "", device_id: str = "", room: str = "", home: str = "", value: Any = 1) -> ControlToolResult:
    """Set fan speed on any fan-speed-capable device such as a fan, air conditioner, or purifier."""
    return await control_device("set_fan_speed", device_name=device_name, device_id=device_id, room=room, home=home, value=value, refresh=True)


@mcp.tool(name="set_cover_position")
async def set_cover_position(device_name: str = "", device_id: str = "", room: str = "", home: str = "", value: int = 50) -> ControlToolResult:
    """Set position for any cover-capable device such as a curtain or blind."""
    return await control_device("set_cover_position", device_name=device_name, device_id=device_id, room=room, home=home, value=value, refresh=True)


@mcp.tool(name="list_scenes")
async def list_scenes(home_name: str = "", home_id: str = "") -> SceneListToolResult:
    """List scenes globally or within a specific home."""
    adapter = get_adapter()
    if not adapter:
        return build_result(False, "Adapter not initialized")

    try:
        await ensure_connected(adapter)
        scenes = await list_normalized_scenes(adapter, home_name=home_name, home_id=home_id)
        return build_result(True, f"Loaded {len(scenes)} scenes", scenes=scenes, count=len(scenes))
    except Exception as exc:
        logger.error(f"Failed to list scenes: {exc}")
        return build_error_result(exc)


@mcp.tool(name="execute_scene")
async def execute_scene(scene_name: str = "", scene_id: str = "", home_name: str = "", home_id: str = "") -> SceneExecutionToolResult:
    """Execute a scene by friendly name or scene id."""
    adapter = get_adapter()
    if not adapter:
        return build_result(False, "Adapter not initialized")

    try:
        await ensure_connected(adapter)
        scene = await resolve_scene(adapter, scene_name=scene_name, scene_id=scene_id, home_name=home_name, home_id=home_id)
        executed = await adapter.run_scene(scene["scene_id"], scene["home_id"] or None)
        return build_result(True, f"Executed scene {scene['name']}", scene=scene, executed=executed)
    except Exception as exc:
        logger.error(f"Failed to execute scene: {exc}")
        return build_error_result(exc)


@mcp.tool(name="get_consumable_items")
async def get_consumable_items(home_name: str = "", home_id: str = "") -> ConsumableItemsToolResult:
    """Get consumable items globally or for a specific home."""
    adapter = get_adapter()
    if not adapter:
        return build_result(False, "Adapter not initialized")

    try:
        await ensure_connected(adapter)
        if home_name or home_id:
            home = await resolve_home(adapter, home_name=home_name, home_id=home_id)
            items = await adapter.get_consumable_items(home["home_id"])
        else:
            items = []
            for home in await adapter.get_homes():
                home_summary = normalize_home(home)
                items.extend(await adapter.get_consumable_items(home_summary["home_id"]))
        return build_result(True, f"Loaded {len(items)} consumable items", items=items, count=len(items))
    except Exception as exc:
        logger.error(f"Failed to get consumable items: {exc}")
        return build_error_result(exc)


@mcp.tool(name="control_by_intent")
async def control_by_intent(
    query: str,
    room: str = "",
    home: str = "",
    prefer_device_type: str = "",
) -> IntentControlToolResult:
    """Route a natural-language-like smart-home request to the best product tool."""
    adapter = get_adapter()
    if not adapter:
        return build_result(False, "Adapter not initialized")

    try:
        await ensure_connected(adapter)
        known_rooms = await get_known_room_names(adapter)
        parsed = infer_intent(query, fallback_room_hints=FALLBACK_ROOM_HINTS, known_rooms=known_rooms)
        resolved_room = room or parsed.get("room", "")
        device_query = parsed.get("device_query", "").strip()

        if parsed["intent"] == "execute_scene":
            payload = extract_structured_content(
                await execute_scene(scene_name=parsed.get("scene_name", ""), home_name=home)
            )
            return build_result(
                bool(payload.get("success")),
                payload.get("message", "Executed scene"),
                route="scene",
                parsed_intent=parsed,
                result=payload,
            )

        if parsed["intent"] == "list_devices":
            payload = extract_structured_content(await list_devices(
                query=parsed.get("device_query", ""),
                room=resolved_room,
                home=home,
                device_type=prefer_device_type,
            ))
            return build_result(
                bool(payload.get("success")),
                payload.get("message", "Listed devices"),
                route="device_list",
                parsed_intent=parsed,
                result=payload,
            )

        if parsed["intent"] == "get_device":
            payload = extract_structured_content(await get_device(
                device_name=device_query,
                room=resolved_room,
                home=home,
                device_type=prefer_device_type,
                refresh=True,
            ))
            return build_result(
                bool(payload.get("success")),
                payload.get("message", "Loaded device"),
                route="device_status",
                parsed_intent=parsed,
                result=payload,
            )

        if parsed["intent"] in OPERATION_CAPABILITY_MAP or parsed["intent"] == "toggle":
            if not device_query:
                return build_result(False, "No target device could be inferred from the request", parsed_intent=parsed)

            device = await resolve_device(
                adapter,
                device_name=device_query,
                room=resolved_room,
                home=home,
                device_type=prefer_device_type,
                refresh=True,
            )
            profile = await get_device_profile(adapter, device["device_id"])
            supported_lookup = {
                item["operation"]: item["enabled"]
                for item in profile.get("supported_operations", [])
            }
            if supported_lookup.get(parsed["intent"], False):
                kwargs: Dict[str, Any] = {
                    "operation": parsed["intent"],
                    "device_id": device["device_id"],
                    "refresh": True,
                }
                if "value" in parsed:
                    kwargs["value"] = parsed["value"]
                payload = extract_structured_content(await control_device(**kwargs))
                return build_result(
                    bool(payload.get("success")),
                    payload.get("message", "Controlled device"),
                    route="standard_operation",
                    parsed_intent=parsed,
                    result=payload,
                )

            fallback_payload = extract_structured_content(await control_device_with_profile_fallback(
                adapter,
                query=query,
                device_name=device_query,
                room=resolved_room,
                home=home,
                prefer_device_type=prefer_device_type,
                parsed_intent=parsed,
            ))
            fallback_result = build_result(
                bool(fallback_payload.get("success")),
                (
                    f"Fell back to profile-driven control for {device['name']}"
                    if fallback_payload.get("success")
                    else f"Profile-driven fallback did not succeed for {device['name']}"
                ),
                parsed_intent=parsed,
                fallback_mode="profile_driven",
                fallback_result=fallback_payload,
            )
            return fallback_result

        return build_result(
            False,
            "Could not route the request to a supported smart-home intent",
            parsed_intent=parsed,
        )
    except Exception as exc:
        logger.error(f"Failed to control by intent: {exc}")
        fallback_rooms = await get_known_room_names(adapter) if adapter and adapter.connected else None
        return build_error_result(
            exc,
            parsed_intent=infer_intent(query, fallback_room_hints=FALLBACK_ROOM_HINTS, known_rooms=fallback_rooms),
        )


@mcp.tool()
async def ping(message: str = "hello") -> PingToolResult:
    """Test server connectivity."""
    return build_result(True, f"pong: {message}", server=SERVER_NAME)


def main():
    logger.info("Initializing Mijia adapter...")
    adapter = get_adapter()
    if not adapter:
        logger.error("Failed to initialize Mijia adapter")
        raise SystemExit(1)
    logger.info("Starting MCP server...")
    mcp.run()


if __name__ == "__main__":
    main()
