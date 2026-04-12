"""Mijia device adapter based on MijiaAPI"""
from typing import Dict, List, Any, Optional
from html import escape
from mijiaAPI import mijiaAPI, mijiaDevice
from config.mijia_config import load_mijia_config, MijiaConfig
from utils.logger import get_logger
from utils.auth_manager import AuthDataManager
import subprocess
import sys
import traceback
import webbrowser
from datetime import datetime
import threading
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from PIL import Image
from qrcode import QRCode

_LOGGER = get_logger(__name__)

class MijiaAdapter:
    """Mijia device adapter"""

    def __init__(self):
        """Initialize adapter"""
        self._api: Optional[mijiaAPI] = None
        self._auth_data: Optional[Dict[str, Any]] = None
        self._connected = False
        self._devices: Dict[str, mijiaDevice] = {}
        self._device_infos: Dict[str, Dict[str, Any]] = {}
        self._homes_cache: List[Dict[str, Any]] = []
        self._config: Optional[MijiaConfig] = None
        self._device_status_cache: Dict[str, Dict[str, Any]] = {}
        self._last_status_update: Optional[datetime] = None
        self._scene_home_map: Dict[str, str] = {}
        self._last_qr_login_url: Optional[str] = None
        self._last_qr_generated_at: Optional[str] = None
        self._config = load_mijia_config()
        self._auth_manager = AuthDataManager()
        # Patch mijiaAPI to avoid encoding issues with QR code display
        self._patch_qr_display()
    
    def _patch_qr_display(self):
        """Patch mijiaAPI's QR display method to avoid encoding issues

        The original mijiaAPI._print_qr method tries to print Unicode block
        characters to the terminal using qr.print_ascii(), which causes
        encoding errors on some systems.
        
        This patch replaces the method to only save the QR code as a PNG file,
        avoiding the problematic ASCII output while maintaining functionality.
        """
        def write_qr_html(html_path: Path, qr_path: Path, loginurl: str) -> None:
            html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Mijia Login QR</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f5f1e8;
      --panel: #fffdf8;
      --text: #1f2937;
      --muted: #6b7280;
      --accent: #d97706;
      --border: #eadfce;
    }}
    body {{
      margin: 0;
      font-family: Georgia, "Times New Roman", serif;
      background: radial-gradient(circle at top, #fff8eb 0%, var(--bg) 58%, #efe7d8 100%);
      color: var(--text);
    }}
    main {{
      max-width: 560px;
      margin: 5vh auto;
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 24px;
      padding: 28px;
      box-shadow: 0 24px 60px rgba(64, 42, 18, 0.12);
    }}
    h1 {{ margin: 0 0 10px; font-size: 2rem; }}
    p {{ line-height: 1.6; }}
    img {{
      display: block;
      width: min(100%, 360px);
      margin: 24px auto;
      border-radius: 16px;
      border: 1px solid var(--border);
      background: white;
      padding: 14px;
    }}
    .meta {{
      color: var(--muted);
      font-size: 0.95rem;
      overflow-wrap: anywhere;
    }}
    a {{ color: var(--accent); }}
    code {{
      background: #f8f1e5;
      padding: 0.15rem 0.35rem;
      border-radius: 6px;
    }}
  </style>
</head>
<body>
  <main>
    <h1>Mijia Login QR</h1>
    <p>Use the Mijia app to scan this QR code and complete login.</p>
    <img src="{escape(qr_path.name)}" alt="Mijia login QR code" />
    <p class="meta">QR image: <code>{escape(str(qr_path))}</code></p>
    <p class="meta">Login URL: <a href="{escape(loginurl)}">{escape(loginurl)}</a></p>
  </main>
</body>
</html>
"""
            html_path.write_text(html, encoding="utf-8")

        def open_with_system_viewer(path: Path) -> bool:
            try:
                if sys.platform == "darwin":
                    subprocess.Popen(["open", str(path)])
                    _LOGGER.info("Opened QR artifact with macOS default app")
                    return True
                if sys.platform.startswith("linux"):
                    if subprocess.call(["which", "xdg-open"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0:
                        subprocess.Popen(["xdg-open", str(path)])
                        _LOGGER.info("Opened QR artifact with xdg-open")
                        return True
                    raise RuntimeError("xdg-open not found")
                if sys.platform == "win32":
                    subprocess.Popen(["cmd", "/c", "start", "", str(path)], shell=False)
                    _LOGGER.info("Opened QR artifact with Windows shell")
                    return True
            except Exception as exc:
                _LOGGER.error(f"Failed to open QR artifact with system viewer: {exc}")
            return False

        def open_qr_artifact(qr_path: Path, html_path: Path, loginurl: str) -> bool:
            mode = getattr(self._config, "qr_open_mode", "browser") if self._config else "browser"
            if mode == "none":
                _LOGGER.info("Skipping automatic QR open because MIJIA_QR_OPEN_MODE=none")
                return False

            if mode == "browser":
                try:
                    opened = webbrowser.open(html_path.resolve().as_uri())
                    if opened:
                        _LOGGER.info("Opened QR page in the default browser")
                        return True
                    _LOGGER.warning("Could not open QR page in the default browser, falling back to local image viewers")
                except Exception as exc:
                    _LOGGER.warning(f"Failed to open QR page in browser, falling back to local image viewers: {exc}")

            if open_with_system_viewer(qr_path):
                return True

            try:
                img = Image.open(qr_path)
                img.show()
                _LOGGER.info("Opened QR code image with Pillow fallback")
                return True
            except Exception as exc:
                _LOGGER.warning(f"Failed to show QR code with Pillow fallback: {exc}")

            _LOGGER.info(f'Please open QR image manually: {qr_path}')
            _LOGGER.info(f'Fallback login URL: {loginurl}')
            return False

        def safe_print_qr(loginurl: str, box_size: int = 10) -> None:
            """Safe QR code display that avoids encoding issues"""
            qr_path = self._auth_manager.get_file_path().parent / "qr.png"
            qr_html_path = self._auth_manager.get_file_path().parent / "qr.html"
            qr_path.parent.mkdir(parents=True, exist_ok=True)
            self._last_qr_login_url = loginurl
            self._last_qr_generated_at = datetime.now().isoformat()
            _LOGGER.info('请使用米家APP扫描二维码')
            _LOGGER.info(f'QR code will be saved as {qr_path}')
            _LOGGER.info(f'QR browser page will be saved as {qr_html_path}')
            _LOGGER.info(f'QR login URL: {loginurl}')
            try:
                qr = QRCode(border=1, box_size=box_size)
                qr.add_data(loginurl)
                qr.make_image().save(qr_path)
                write_qr_html(qr_html_path, qr_path, loginurl)
                _LOGGER.info(f'QR code saved successfully as {qr_path}')
                _LOGGER.info(f'QR browser page saved successfully as {qr_html_path}')
                opened = open_qr_artifact(qr_path, qr_html_path, loginurl)

                # 仅在显式 none 模式或自动打开失败时，才强调终端二维码兜底
                open_mode = getattr(self._config, "qr_open_mode", "browser") if self._config else "browser"
                if open_mode == "none" or not opened:
                    try:
                        qr.print_ascii(invert=True, tty=True)
                    except Exception:
                        try:
                            qr.print_ascii(invert=True, tty=False)
                        except Exception:
                            _LOGGER.info(f'Fallback login URL: {loginurl}')
                
            except Exception as e:
                _LOGGER.error(f'Failed to save QR code: {e}')
                raise
        
        # Replace the problematic _print_qr method in mijiaAPI 3.x
        mijiaAPI._print_qr = staticmethod(safe_print_qr)
        
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

            auth_path = str(self._auth_manager.get_file_path())
            auth_data = self._auth_manager.load()
            if auth_data and not self._auth_manager.validate(auth_data):
                _LOGGER.warning("Cached authentication data is invalid, starting fresh login...")
                self._auth_manager.clear()

            _LOGGER.info("Initializing Mijia API...")
            self._api = mijiaAPI(auth_path)

            if not self._api.available:
                if not self._config.enableQR:
                    _LOGGER.warning("mijiaAPI 3.x only supports QR login; forcing QR flow")
                _LOGGER.info("Starting QR code login flow")
                self._auth_data = self._api.login()
            else:
                self._auth_data = self._api.auth_data
            
            # 检查 API 是否可用
            if self._api.available:
                self._connected = True
                _LOGGER.info("Successfully connected to Mijia cloud service")
                return True
            else:
                error_msg = "Mijia API unavailable, possibly due to expired authentication data or network issues"
                _LOGGER.error(error_msg)
                self._auth_data = None
                if self._auth_manager.clear():
                    _LOGGER.info("Expired authentication data cleared")
                else:
                    _LOGGER.warning("Failed to clear expired authentication data")
                
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
            self._device_infos.clear()
            self._homes_cache = []
            _LOGGER.info("Disconnected from Mijia cloud service")
        except Exception as e:
            _LOGGER.error(f"Error during disconnection: {e}")
    
    def clear_auth_data(self) -> bool:
        """清除认证数据
        
        Returns:
            bool: 是否清除成功
        """
        self._auth_data = None
        return self._auth_manager.clear()
    
    def has_valid_auth_data(self) -> bool:
        """检查是否有有效的认证数据
        
        Returns:
            bool: 是否有有效的认证数据
        """
        if self._auth_data:
            return self._auth_manager.validate(self._auth_data)
        return self._auth_manager.exists() and self._auth_manager.validate()
    
    def get_auth_file_path(self) -> Path:
        """获取认证数据文件路径
        
        Returns:
            Path: 认证数据文件路径
        """
        return self._auth_manager.get_file_path()

    def get_qr_image_path(self) -> Path:
        """Return the generated QR image path."""
        return self._auth_manager.get_file_path().parent / "qr.png"

    def get_qr_page_path(self) -> Path:
        """Return the generated QR browser page path."""
        return self._auth_manager.get_file_path().parent / "qr.html"

    def get_qr_status(self) -> Dict[str, Any]:
        """Return the latest QR login artifact status."""
        qr_image_path = self.get_qr_image_path()
        qr_page_path = self.get_qr_page_path()
        return {
            "enabled": bool(self._config.enableQR) if self._config else True,
            "open_mode": getattr(self._config, "qr_open_mode", "browser") if self._config else "browser",
            "image_path": str(qr_image_path),
            "image_exists": qr_image_path.exists(),
            "page_path": str(qr_page_path),
            "page_exists": qr_page_path.exists(),
            "login_url": self._last_qr_login_url,
            "generated_at": self._last_qr_generated_at,
        }

    def open_qr_artifacts(self) -> bool:
        """Open existing QR artifacts using the configured mode."""
        qr_status = self.get_qr_status()
        qr_image_path = Path(qr_status["image_path"])
        qr_page_path = Path(qr_status["page_path"])
        login_url = qr_status.get("login_url")
        open_mode = qr_status.get("open_mode") or "browser"

        if open_mode == "none":
            _LOGGER.info("Skipping QR artifact open because MIJIA_QR_OPEN_MODE=none")
            return False

        if open_mode == "browser" and qr_page_path.exists():
            try:
                opened = webbrowser.open(qr_page_path.resolve().as_uri())
                if opened:
                    _LOGGER.info("Opened saved QR page in the default browser")
                    return True
            except Exception as exc:
                _LOGGER.error(f"Failed to open saved QR page in browser: {exc}")

        if qr_image_path.exists():
            try:
                if sys.platform == "darwin":
                    subprocess.Popen(["open", str(qr_image_path)])
                    _LOGGER.info("Opened saved QR image with macOS default app")
                    return True
                if sys.platform.startswith("linux"):
                    if subprocess.call(["which", "xdg-open"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0:
                        subprocess.Popen(["xdg-open", str(qr_image_path)])
                        _LOGGER.info("Opened saved QR image with xdg-open")
                        return True
                if sys.platform == "win32":
                    subprocess.Popen(["cmd", "/c", "start", "", str(qr_image_path)], shell=False)
                    _LOGGER.info("Opened saved QR image with Windows shell")
                    return True
            except Exception as exc:
                _LOGGER.error(f"Failed to open saved QR image with system viewer: {exc}")

            try:
                img = Image.open(qr_image_path)
                img.show()
                _LOGGER.info("Opened saved QR image with Pillow fallback")
                return True
            except Exception as exc:
                _LOGGER.error(f"Failed to show saved QR image: {exc}")

        if qr_page_path.exists():
            _LOGGER.info(f"Please open QR page manually: {qr_page_path}")
        if qr_image_path.exists():
            _LOGGER.info(f"Please open QR image manually: {qr_image_path}")
        if login_url:
            _LOGGER.info(f"Fallback login URL: {login_url}")
        return False
    
    def _create_device_sync(self, device_data: Dict[str, Any], index: int) -> tuple:
        """同步创建设备对象的辅助方法
        
        Args:
            device_data: 设备数据
            index: 设备索引
            
        Returns:
            tuple: (success: bool, device: mijiaDevice or None, error_info: str or None)
        """
        try:
            did = device_data.get("did")
            if not did:
                return False, None, f"Device{index}(missing did)"
            
            model = device_data.get("model")
            if not model:
                return False, None, f"Device{index}(missing model)"
            
            device = mijiaDevice(self._api, did=did)
            
            return True, device, None
            
        except Exception as e:
            device_name = device_data.get('name', f'Device{index}')
            return False, None, device_name
    
    async def discover_devices(self, max_workers: int = 5) -> List[mijiaDevice]:
        """Discover devices with concurrent processing
        
        Args:
            max_workers: 最大并发工作线程数，默认为5

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
            self._device_infos = {
                str(item.get("did")): item for item in raw_device_infos if item.get("did")
            }
            
            if not raw_device_infos:
                _LOGGER.warning("No devices discovered")
                return []
            
            _LOGGER.info(f"Retrieved {len(raw_device_infos)} device information from cloud")
            _LOGGER.info(f"Using concurrent processing with {max_workers} workers to optimize performance")
            
            device_infos = []
            failed_devices = []
            
            original_get_devices_list = self._api.get_devices_list
            self._api.get_devices_list = lambda home_id=None: raw_device_infos if home_id is None else [
                item for item in raw_device_infos if str(item.get("home_id")) == str(home_id)
            ]

            try:
                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    future_to_index = {
                        executor.submit(self._create_device_sync, device_data, i): i
                        for i, device_data in enumerate(raw_device_infos)
                    }

                    for future in as_completed(future_to_index):
                        index = future_to_index[future]
                        try:
                            success, device, error_info = future.result()

                            if success and device:
                                self._devices[device.did] = device
                                device_infos.append(device)
                                _LOGGER.debug(f"Successfully created device object: {device.name} ({device.did})")
                            else:
                                failed_devices.append(error_info or f"Device{index}")
                                _LOGGER.warning(f"Failed to create device {index}: {error_info}")

                        except Exception as e:
                            failed_devices.append(f"Device{index}")
                            _LOGGER.warning(f"Exception processing device {index}: {e}")
            finally:
                self._api.get_devices_list = original_get_devices_list
            
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

    async def get_device_properties(self, device_id: str) -> List:
        """Get device property list

        Args:
            device_id: Device ID

        Returns:
            List: Device property list
        """
        device = self._get_device(device_id)
        
        try:
            # Get device specification information
            propsMap = device.prop_list
            if not propsMap:
                return []
            return list(map(lambda x: x, propsMap.values()))
        except Exception as e:
            _LOGGER.error(f"Failed to get device properties for {device_id}: {e}")
            raise
    
    async def get_device_actions(self, device_id: str) -> List:
        """Get device action list

        Args:
            device_id: Device ID

        Returns:
            List: Device action list
        """
        if not self._connected:
            raise RuntimeError("Not connected to Mijia cloud service")
        
        if device_id not in self._devices:
            raise ValueError(f"Device {device_id} not found")
        
        try:
            device = self._devices[device_id]
            if not device.action_list:
                return []
            return list(map(lambda x: x, device.action_list.values()))
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
            result = self._api.get_devices_prop({
                "did": device_id,
                "siid": siid,
                "piid": piid
            })

            if result.get('code') == 0:
                return result.get('value')

            raise RuntimeError(f"Failed to get property: {result.get('code')}")
                
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
            result = self._api.set_devices_prop({
                "did": device_id,
                "siid": siid,
                "piid": piid,
                "value": value
            })

            success = result.get('code') in (0, 1)
            if success:
                _LOGGER.info(f"Successfully set property {siid}:{piid} = {value} (device: {device_id})")
            else:
                _LOGGER.warning(f"Failed to set property {siid}:{piid} = {value} (device: {device_id}), error code: {result.get('code')}")
            return success
                
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
                "value": params or []
            })
            
            if result.get('code') == 0:
                _LOGGER.info(f"Successfully executed action {siid}:{aiid} (device: {device_id})")
                return result.get('out', [])
            else:
                raise RuntimeError(f"Action execution failed, error code: {result.get('code')}")
                
        except Exception as e:
            _LOGGER.error(f"Failed to execute action: {e}")
            raise
    
    async def get_homes(self) -> List[Dict[str, Any]]:
        """Get home list

        Returns:
            List[Dict[str, Any]]: Home list
        """
        if not self._connected:
            raise RuntimeError("Not connected to Mijia cloud service")
        
        try:
            homes = self._api.get_homes_list()
            self._homes_cache = homes
            return homes
        except Exception as e:
            _LOGGER.error(f"Failed to get home list: {e}")
            raise

    async def get_scenes_list(self, home_id: str) -> List[Dict[str, Any]]:
        """Get scene list

        Args:
            home_id: Home ID

        Returns:
            List[Dict[str, Any]]: Scene list
        """
        if not self._connected:
            raise RuntimeError("Not connected to Mijia cloud service")
        
        try:
            scenes = self._api.get_scenes_list(home_id)
            for scene in scenes:
                scene_key = scene.get("scene_id") or scene.get("id")
                if scene_key:
                    self._scene_home_map[str(scene_key)] = str(home_id)
            return scenes
        except Exception as e:
            _LOGGER.error(f"Failed to get scene list: {e}")
            raise

    async def run_scene(self, scene_id: str, home_id: Optional[str] = None) -> bool:
        """Run scene

        Args:
            scene_id: Scene ID

        Returns:
            bool: Whether running is successful
        """
        if not self._connected:
            raise RuntimeError("Not connected to Mijia cloud service")
        
        try:
            resolved_home_id = home_id or self._scene_home_map.get(str(scene_id))
            if resolved_home_id is None:
                scenes = self._api.get_scenes_list()
                for scene in scenes:
                    scene_key = scene.get("scene_id") or scene.get("id")
                    mapped_home_id = scene.get("home_id")
                    if scene_key and mapped_home_id:
                        self._scene_home_map[str(scene_key)] = str(mapped_home_id)
                resolved_home_id = self._scene_home_map.get(str(scene_id))

            if resolved_home_id is None:
                raise RuntimeError(f"Unable to resolve home_id for scene {scene_id}")

            return bool(self._api.run_scene(scene_id, resolved_home_id))
        except Exception as e:
            _LOGGER.error(f"Failed to run scene: {e}")
            raise

    async def get_consumable_items(self, home_id: str, owner_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get consumable item list

        Args:
            home_id (str): home_id from get_homes_list
            owner_id (int, optional): UserID,default is None, provide owner_id when home_id is shared

        Returns:
            List[Dict[str, Any]]: Consumable item list
        """
        if not self._connected:
            raise RuntimeError("Not connected to Mijia cloud service")
        
        try:
            if owner_id is not None:
                _LOGGER.warning("owner_id is ignored by mijiaAPI 3.x; using home_id only")
            items = self._api.get_consumable_items(home_id)
            return items
        except Exception as e:
            _LOGGER.error(f"Failed to get consumable item list: {e}")
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
            try:
                self._devices[device_id] = mijiaDevice(self._api, did=device_id)
            except Exception as e:
                raise RuntimeError(f"Device {device_id} not found or failed to initialize: {e}") from e
        
        return self._devices[device_id]

    def _build_room_lookup(self) -> Dict[str, Dict[str, str]]:
        """Build room/home lookup keyed by device id and room id when available."""
        room_lookup: Dict[str, Dict[str, str]] = {}
        for home in self._homes_cache:
            home_id = str(home.get("id", ""))
            home_name = home.get("name")
            for room in home.get("roomlist", []) or []:
                room_id = str(room.get("id", ""))
                room_meta = {
                    "room_name": room.get("name"),
                    "room_id": room_id,
                    "home_id": home_id,
                    "home_name": home_name,
                }
                if room_id:
                    room_lookup[room_id] = room_meta
                for did in room.get("dids", []) or []:
                    did_key = str(did or "")
                    if did_key:
                        room_lookup[did_key] = room_meta
        return room_lookup

    async def list_device_infos(self, refresh: bool = False) -> List[Dict[str, Any]]:
        """Return normalized raw device info entries."""
        if not self._connected:
            raise RuntimeError("Not connected to Mijia cloud service")

        if refresh or not self._device_infos:
            raw_device_infos = self._api.get_devices_list()
            self._device_infos = {
                str(item.get("did")): item for item in raw_device_infos if item.get("did")
            }

        if not self._homes_cache:
            self._homes_cache = self._api.get_homes_list()

        room_lookup = self._build_room_lookup()
        normalized_devices: List[Dict[str, Any]] = []

        for did, info in self._device_infos.items():
            normalized = dict(info)
            room_id = str(normalized.get("room_id", "") or "")
            did_key = str(did or "")
            room_meta = room_lookup.get(did_key) or room_lookup.get(room_id, {})
            normalized.update({
                "did": did,
                "room_id": str(room_meta.get("room_id") or room_id or normalized.get("room_id") or ""),
                "room_name": room_meta.get("room_name") or normalized.get("room_name"),
                "home_id": str(normalized.get("home_id") or room_meta.get("home_id") or ""),
                "home_name": room_meta.get("home_name") or normalized.get("home_name"),
            })
            normalized_devices.append(normalized)

        return normalized_devices

    async def resolve_devices(
        self,
        query: str = "",
        room: str = "",
        home: str = "",
        device_type: str = "",
        online_only: bool = False,
    ) -> List[Dict[str, Any]]:
        """Resolve devices by user-friendly filters."""
        devices = await self.list_device_infos(refresh=not self._device_infos)
        resolved: List[Dict[str, Any]] = []

        query_lower = query.strip().lower()
        room_lower = room.strip().lower()
        home_lower = home.strip().lower()
        type_lower = device_type.strip().lower()

        for device in devices:
            device_name = str(device.get("name", "") or "").lower()
            model = str(device.get("model", "") or "").lower()
            did = str(device.get("did", "") or "").lower()
            room_name = str(device.get("room_name", "") or "").lower()
            home_name = str(device.get("home_name", "") or "").lower()

            if query_lower and query_lower not in " ".join([device_name, model, did, room_name, home_name]):
                continue
            if room_lower and room_lower not in str(device.get("room_name", "") or "").lower():
                continue
            if home_lower and home_lower not in str(device.get("home_name", "") or "").lower():
                continue
            if type_lower and type_lower not in str(device.get("model", "") or "").lower():
                continue
            if online_only and not bool(device.get("isOnline", device.get("online", True))):
                continue
            resolved.append(device)

        return resolved

    def _rank_device_matches(
        self,
        devices: List[Dict[str, Any]],
        device_name: str = "",
    ) -> List[Dict[str, Any]]:
        """Rank matches with strong preference for user-defined device names."""
        if not device_name.strip():
            return devices

        name_query = device_name.strip().lower()

        exact_name_matches = [
            device for device in devices
            if str(device.get("name", "")).strip().lower() == name_query
        ]
        if exact_name_matches:
            return exact_name_matches

        fuzzy_name_matches = [
            device for device in devices
            if name_query in str(device.get("name", "")).strip().lower()
        ]
        if fuzzy_name_matches:
            return fuzzy_name_matches

        prefix_name_matches = [
            device for device in devices
            if str(device.get("name", "")).strip().lower().startswith(name_query)
        ]
        if prefix_name_matches:
            return prefix_name_matches

        model_matches = [
            device for device in devices
            if name_query in str(device.get("model", "")).strip().lower()
        ]
        if model_matches:
            return model_matches

        did_matches = [
            device for device in devices
            if name_query == str(device.get("did", "")).strip().lower()
        ]
        if did_matches:
            return did_matches

        return devices

    async def resolve_single_device(
        self,
        device_name: str = "",
        device_id: str = "",
        room: str = "",
        home: str = "",
        device_type: str = "",
    ) -> Dict[str, Any]:
        """Resolve a single device, raising useful errors on ambiguity."""
        if device_id:
            devices = await self.resolve_devices(query=device_id, room=room, home=home, device_type=device_type)
            for device in devices:
                if str(device.get("did")) == str(device_id):
                    return device
            raise RuntimeError(f"Device with id {device_id} not found")

        matches = await self.resolve_devices(
            query=device_name,
            room=room,
            home=home,
            device_type=device_type,
        )
        matches = self._rank_device_matches(matches, device_name=device_name)

        if not matches:
            raise RuntimeError(f"No device matched name={device_name!r}, room={room!r}, home={home!r}")
        if len(matches) > 1:
            candidates = [
                f"{item.get('name')} ({item.get('room_name') or 'unknown room'} / {item.get('home_name') or 'unknown home'})"
                for item in matches[:5]
            ]
            raise RuntimeError(f"Multiple devices matched. Candidates: {candidates}")
        return matches[0]

    async def resolve_scene(
        self,
        scene_name: str = "",
        scene_id: str = "",
        home_id: str = "",
        home_name: str = "",
    ) -> Dict[str, Any]:
        """Resolve scene by id or friendly name."""
        if home_id:
            scenes = self._api.get_scenes_list(home_id)
        else:
            scenes = self._api.get_scenes_list()

        matches: List[Dict[str, Any]] = []
        for scene in scenes:
            scene_key = str(scene.get("scene_id") or scene.get("id") or "")
            scene_home_id = str(scene.get("home_id") or "")
            if scene_key and scene_home_id:
                self._scene_home_map[scene_key] = scene_home_id

            if scene_id and scene_key == str(scene_id):
                return scene

            if scene_name and scene_name.strip().lower() == str(scene.get("name", "")).strip().lower():
                if home_name and home_name.strip().lower() not in str(scene.get("home_name", "")).strip().lower():
                    continue
                matches.append(scene)

        if scene_id:
            raise RuntimeError(f"Scene with id {scene_id} not found")
        if not matches:
            raise RuntimeError(f"No scene matched name={scene_name!r}")
        if len(matches) > 1:
            candidates = [f"{item.get('name')} ({item.get('home_id')})" for item in matches[:5]]
            raise RuntimeError(f"Multiple scenes matched. Candidates: {candidates}")
        return matches[0]

    async def get_property_value_by_name(self, device_id: str, property_name: str) -> Any:
        """Get device property value by logical property name."""
        device = self._get_device(device_id)
        try:
            return device.get(property_name)
        except Exception as e:
            _LOGGER.error(f"Failed to get property {property_name} for {device_id}: {e}")
            raise

    async def set_property_value_by_name(self, device_id: str, property_name: str, value: Any) -> bool:
        """Set device property value by logical property name."""
        device = self._get_device(device_id)
        try:
            device.set(property_name, value)
            _LOGGER.info(f"Successfully set property {property_name} = {value} (device: {device_id})")
            return True
        except Exception as e:
            _LOGGER.error(f"Failed to set property {property_name} for {device_id}: {e}")
            raise

    async def call_action_by_name(self, device_id: str, action_name: str, params: Optional[List[Any]] = None) -> bool:
        """Call device action by logical action name."""
        device = self._get_device(device_id)
        try:
            device.run_action(action_name, params or [])
            _LOGGER.info(f"Successfully executed action {action_name} (device: {device_id})")
            return True
        except Exception as e:
            _LOGGER.error(f"Failed to execute action {action_name} for {device_id}: {e}")
            raise
    
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
