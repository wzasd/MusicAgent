"""
配置加载模块
从 setting.json 文件加载配置并设置环境变量
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, Optional


def load_settings_from_json(json_path: Optional[str] = None) -> Dict[str, Any]:
    """
    从 JSON 文件加载配置
    
    Args:
        json_path: JSON 文件路径，如果为 None 则自动查找 setting.json
        
    Returns:
        配置字典
    """
    if json_path is None:
        # 尝试多个可能的路径
        possible_paths = [
            Path("setting.json"),
            Path(__file__).parent.parent / "setting.json",
            Path.cwd() / "setting.json"
        ]
        
        for path in possible_paths:
            if path.exists():
                json_path = str(path)
                break
        else:
            raise FileNotFoundError("未找到 setting.json 文件")
    
    json_path = Path(json_path)
    if not json_path.exists():
        raise FileNotFoundError(f"配置文件不存在: {json_path}")
    
    with open(json_path, 'r', encoding='utf-8') as f:
        raw = json.load(f)

    # 兼容当前项目的层级结构：
    # {
    #   "settings": { ... 平铺配置 ... },
    #   "WAN_API_SETTINGS": { ... 可选 ... }
    # }
    if isinstance(raw, dict):
        settings = {}
        # 先合并顶层 settings 字段
        if isinstance(raw.get("settings"), dict):
            settings.update(raw["settings"])
        # 其余顶层简单 key 也合并进来（防止以后扩展）
        for k, v in raw.items():
            if k == "settings":
                continue
            # 只保留简单标量配置，避免把嵌套对象错误映射为 env
            if not isinstance(v, dict):
                settings[k] = v
        # 同时把 WAN_API_SETTINGS 暴露出去，便于其他模块使用
        if isinstance(raw.get("WAN_API_SETTINGS"), dict):
            settings["WAN_API_SETTINGS"] = raw["WAN_API_SETTINGS"]
    else:
        settings = raw

    return settings


def setup_environment_from_settings(settings: Optional[Dict[str, Any]] = None) -> None:
    """
    从配置字典设置环境变量
    
    Args:
        settings: 配置字典，如果为 None 则从 setting.json 加载
    """
    if settings is None:
        settings = load_settings_from_json()
    
    # 设置环境变量（如果尚未设置）
    env_mapping = {
        "SILICONFLOW_API_KEY": "SILICONFLOW_API_KEY",
        "SILICONFLOW_BASE_URL": "SILICONFLOW_BASE_URL",
        "SILICONFLOW_CHAT_MODEL": "SILICONFLOW_MODEL",  # 注意：环境变量名不同
        "DASH_SCOPE_API_KEY": "DASH_SCOPE_API_KEY",
        "DASH_SCOPE_BASE_URL": "DASH_SCOPE_BASE_URL",
        "DASH_SCOPE_EMBEDDING_MODEL": "DASH_SCOPE_EMBEDDING_MODEL",
        "TAILYAPI_API_KEY": "TAILYAPI_API_KEY",
        "TAILYAPI_BASE_URL": "TAILYAPI_BASE_URL",
        "SPOTIFY_CLIENT_ID": "SPOTIFY_CLIENT_ID",
        "SPOTIFY_CLIENT_SECRET": "SPOTIFY_CLIENT_SECRET",
    }
    
    for json_key, env_key in env_mapping.items():
        if json_key in settings and settings[json_key]:
            # 强制设置环境变量（覆盖已存在的值）
            os.environ[env_key] = str(settings[json_key])

    # 额外处理 WAN_API_SETTINGS，方便 Python 端也能直接使用 WAN 配置
    wan_settings = settings.get("WAN_API_SETTINGS")
    if isinstance(wan_settings, dict):
        if wan_settings.get("WAN_API_URL"):
            os.environ["WAN_API_URL"] = str(wan_settings["WAN_API_URL"])
        if wan_settings.get("WAN_API_KEY"):
            os.environ["WAN_API_KEY"] = str(wan_settings["WAN_API_KEY"])


def load_and_setup_settings(json_path: Optional[str] = None) -> Dict[str, Any]:
    """
    加载配置并设置环境变量（便捷函数）
    
    Args:
        json_path: JSON 文件路径
        
    Returns:
        配置字典
    """
    settings = load_settings_from_json(json_path)
    setup_environment_from_settings(settings)
    return settings

