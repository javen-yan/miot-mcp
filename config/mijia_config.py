"""Mijia configuration management module"""

import os
from dataclasses import dataclass
from typing import Optional

@dataclass
class MijiaConfig:
    """Mijia configuration"""
    username: Optional[str] = None
    password: Optional[str] = None
    enableQR: bool = True
    qr_open_mode: str = "browser"
    log_level: str = "INFO"
    
    @classmethod
    def from_env(cls) -> 'MijiaConfig':
        """Load configuration from environment variables"""
        enableQR = os.getenv('MIJIA_ENABLE_QR', 'true').lower() == 'true'
        username = os.getenv('MIJIA_USERNAME')
        password = os.getenv('MIJIA_PASSWORD')
        qr_open_mode = os.getenv('MIJIA_QR_OPEN_MODE', 'browser').strip().lower() or 'browser'
        if qr_open_mode not in {"browser", "viewer", "none"}:
            qr_open_mode = "browser"
        log_level = os.getenv('MIJIA_LOG_LEVEL', 'INFO').upper()

        return cls(
            username=username,
            password=password,
            enableQR=enableQR,
            qr_open_mode=qr_open_mode,
            log_level=log_level,
        )

def load_mijia_config() -> MijiaConfig:
    """Load Mijia configuration from environment variables
    Environment variables:
    - MIJIA_USERNAME: Deprecated in mijiaAPI 3.x, no longer used for login
    - MIJIA_PASSWORD: Deprecated in mijiaAPI 3.x, no longer used for login
    - MIJIA_ENABLE_QR: Whether to enable QR code login (optional, default: true)
    - MIJIA_QR_OPEN_MODE: How to open the generated QR code page, supports browser/viewer/none
    - MIJIA_LOG_LEVEL: Log level (optional, default: INFO)
    
    Returns:
        MijiaConfig: Mijia configuration object
    """
    return MijiaConfig.from_env()
