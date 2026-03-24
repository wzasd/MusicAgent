"""
搜索日志存储模块
独立于其他模块，避免循环导入
"""

from typing import Dict, Any, List
from datetime import datetime

# 搜索日志存储（内存中，最近50条）
_search_logs: List[Dict[str, Any]] = []
_MAX_LOGS = 50


def add_search_log(log_entry: Dict[str, Any]):
    """添加搜索日志"""
    global _search_logs
    log_entry["timestamp"] = datetime.now().isoformat()
    _search_logs.insert(0, log_entry)  # 新日志放前面
    if len(_search_logs) > _MAX_LOGS:
        _search_logs = _search_logs[:_MAX_LOGS]


def get_search_logs(limit: int = 20) -> List[Dict[str, Any]]:
    """获取最近搜索日志"""
    return _search_logs[:limit]
