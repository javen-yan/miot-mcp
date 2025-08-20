"""米家配置管理模块"""

import os
from typing import Optional
from dataclasses import dataclass
import yaml
from pathlib import Path


@dataclass
class MijiaConfig:
    """米家配置"""
    username: str
    password: str
    enableQR: bool = False
    
    @classmethod
    def from_env(cls) -> 'MijiaConfig':
        """从环境变量加载配置"""
        enableQR = os.getenv('MIJIA_ENABLEQR', 'false').lower() == 'true'
        username = os.getenv('MIJIA_USERNAME')
        password = os.getenv('MIJIA_PASSWORD')
        
        if not enableQR:
            if not username or not password:
                raise ValueError("MIJIA_USERNAME and MIJIA_PASSWORD environment variables are required")
        
        return cls(username=username, password=password, enableQR=enableQR)
    
    @classmethod
    def from_file(cls, config_path: str) -> 'MijiaConfig':
        """从配置文件加载配置"""
        config_file = Path(config_path)
        if not config_file.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")
        
        with open(config_file, 'r', encoding='utf-8') as f:
            config_data = yaml.safe_load(f)
        
        mijia_config = config_data.get('mijia', {})
        username = mijia_config.get('username')
        password = mijia_config.get('password')
        enableQR = mijia_config.get('enableQR', False)
        
        if not enableQR:
            if not username or not password:
                raise ValueError("username and password are required in config file")
        
        return cls(username=username, password=password, enableQR=enableQR)
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            'username': self.username,
            'password': self.password,
            'enableQR': self.enableQR
        }
    
    def save_to_file(self, config_path: str) -> None:
        """保存到配置文件"""
        config_file = Path(config_path)
        config_file.parent.mkdir(parents=True, exist_ok=True)
        
        config_data = {
            'mijia': {
                'username': self.username,
                'password': self.password,
                'enableQR': self.enableQR
            }
        }
        
        with open(config_file, 'w', encoding='utf-8') as f:
            yaml.dump(config_data, f, default_flow_style=False, allow_unicode=True)


def load_mijia_config(config_path: Optional[str] = None) -> MijiaConfig:
    """加载米家配置
    
    优先级:
    1. 指定的配置文件路径
    2. 默认配置文件 config/mijia.yaml
    3. 环境变量
    
    Args:
        config_path: 配置文件路径
        
    Returns:
        MijiaConfig: 米家配置对象
    """
    # 1. 尝试从指定的配置文件加载
    if config_path:
        try:
            return MijiaConfig.from_file(config_path)
        except (FileNotFoundError, ValueError) as e:
            print(f"Failed to load config from {config_path}: {e}")
    
    # 2. 尝试从默认配置文件加载
    default_config_path = Path(__file__).parent / "mijia.yaml"
    if default_config_path.exists():
        try:
            return MijiaConfig.from_file(str(default_config_path))
        except ValueError as e:
            print(f"Failed to load default config: {e}")
    
    # 3. 尝试从环境变量加载
    try:
        return MijiaConfig.from_env()
    except ValueError as e:
        print(f"Failed to load config from environment: {e}")
    
    raise RuntimeError(
        "Failed to load Mijia configuration. Please provide config file or set environment variables:\n"
        "  - MIJIA_USERNAME\n"
        "  - MIJIA_PASSWORD\n"
        "  - MIJIA_ENABLEQR (optional, default: false)"
    )