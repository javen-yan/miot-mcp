"""Mijia configuration management module"""

import os
from dataclasses import dataclass

@dataclass
class MijiaConfig:
    """Mijia configuration"""
    username: str
    password: str
    enableQR: bool = False
    log_level: str = "INFO"
    
    @classmethod
    def from_env(cls) -> 'MijiaConfig':
        """Load configuration from environment variables"""
        enableQR = os.getenv('MIJIA_ENABLE_QR', 'false').lower() == 'true'
        username = os.getenv('MIJIA_USERNAME')
        password = os.getenv('MIJIA_PASSWORD')
        log_level = os.getenv('MIJIA_LOG_LEVEL', 'INFO').upper()
        
        if not enableQR:
            if not username or not password:
                raise ValueError("MIJIA_USERNAME and MIJIA_PASSWORD environment variables are required")
        
        return cls(username=username, password=password, enableQR=enableQR, log_level=log_level)

def load_mijia_config() -> MijiaConfig:
    """Load Mijia configuration from environment variables
    Environment variables:
    - MIJIA_USERNAME: Mijia account
    - MIJIA_PASSWORD: Mijia password
    - MIJIA_ENABLE_QR: Whether to enable QR code login (optional, default: false)
    - MIJIA_LOG_LEVEL: Log level (optional, default: INFO)
    
    Returns:
        MijiaConfig: Mijia configuration object
    """
    try:
        return MijiaConfig.from_env()
    except ValueError as e:
        print(f"Failed to load config from environment: {e}")

    raise RuntimeError(
        "Failed to load Mijia configuration. Please provide config file or set environment variables:\n"
        "  - MIJIA_USERNAME\n"
        "  - MIJIA_PASSWORD\n"
        "  - MIJIA_ENABLE_QR (optional, default: false)\n"
        "  - MIJIA_LOG_LEVEL (optional, default: INFO)"
    )