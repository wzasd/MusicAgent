"""
性能监控工具模块
提供统一的性能计时和监控功能
"""

import time
import functools
import asyncio
from typing import Callable, Any, Dict, List, Optional
from contextvars import ContextVar
from dataclasses import dataclass, field


@dataclass
class TimingEntry:
    """单次计时记录"""
    duration_ms: float
    timestamp: float
    path: str
    metadata: Dict[str, Any] = field(default_factory=dict)


class PerformanceTimer:
    """性能计时器 - 支持嵌套和并发"""

    def __init__(self):
        self.timings: Dict[str, List[TimingEntry]] = {}
        self.token_usage: Dict[str, Dict[str, int]] = {}
        self.current_path: List[str] = []
        self._start_times: Dict[str, float] = {}

    def start(self, name: str, metadata: Optional[Dict] = None):
        """开始计时一个操作"""
        self._start_times[name] = time.time()
        self.current_path.append(name)
        return self

    def end(self, name: str, metadata: Optional[Dict] = None):
        """结束计时并记录结果"""
        if name in self._start_times:
            duration_ms = (time.time() - self._start_times[name]) * 1000
            self.record_timing(name, duration_ms, metadata)
            if name in self.current_path:
                self.current_path.remove(name)
            del self._start_times[name]

    def record_timing(self, name: str, duration_ms: float, metadata: Optional[Dict] = None):
        """记录一次计时结果"""
        if name not in self.timings:
            self.timings[name] = []

        entry = TimingEntry(
            duration_ms=duration_ms,
            timestamp=time.time(),
            path='.'.join(self.current_path),
            metadata=metadata or {}
        )
        self.timings[name].append(entry)

    def record_tokens(self, provider: str, prompt_tokens: int, completion_tokens: int):
        """记录token使用量"""
        if provider not in self.token_usage:
            self.token_usage[provider] = {'prompt_tokens': 0, 'completion_tokens': 0, 'total_tokens': 0}

        self.token_usage[provider]['prompt_tokens'] += prompt_tokens
        self.token_usage[provider]['completion_tokens'] += completion_tokens
        self.token_usage[provider]['total_tokens'] += prompt_tokens + completion_tokens

    def get_summary(self) -> Dict[str, Any]:
        """获取性能摘要"""
        summary = {
            'timings': {},
            'token_usage': self.token_usage,
            'total_time_ms': 0
        }

        for name, entries in self.timings.items():
            durations = [e.duration_ms for e in entries]
            summary['timings'][name] = {
                'count': len(durations),
                'total_ms': round(sum(durations), 2),
                'avg_ms': round(sum(durations) / len(durations), 2) if durations else 0,
                'min_ms': round(min(durations), 2) if durations else 0,
                'max_ms': round(max(durations), 2) if durations else 0,
            }

        # 计算总时间（根级别操作的和）
        summary['total_time_ms'] = round(sum(
            t['total_ms'] for t in summary['timings'].values()
        ), 2)

        return summary

    def get_flat_timings(self) -> Dict[str, float]:
        """获取扁平化的计时结果（用于向后兼容）"""
        flat = {}
        for name, entries in self.timings.items():
            if entries:
                # 取最后一次的耗时
                flat[f'{name}_ms'] = round(entries[-1].duration_ms, 2)
            # 如果有多个相同类型的操作，累加
            total = sum(e.duration_ms for e in entries)
            flat[f'{name}_total_ms'] = round(total, 2)
        return flat


# 存储当前请求的指标数据
current_metrics: ContextVar[Optional[Dict[str, Any]]] = ContextVar('current_metrics', default=None)


def timed(name: Optional[str] = None, track_tokens: bool = False):
    """
    装饰器：自动为函数添加性能计时

    用法:
        @timed("spotify_search")
        async def search_tracks(self, query: str): ...

        @timed("llm_call", track_tokens=True)
        async def call_llm(self, prompt: str): ...
    """
    def decorator(func: Callable) -> Callable:
        timer_name = name or func.__name__

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            timer = get_current_timer()
            if timer is None:
                return await func(*args, **kwargs)

            start_time = time.time()
            timer.current_path.append(timer_name)

            try:
                result = await func(*args, **kwargs)

                # 计算耗时
                duration_ms = (time.time() - start_time) * 1000

                # 提取元数据
                metadata = {'function': func.__name__}

                # 如果启用了token追踪，尝试从结果中提取
                if track_tokens and isinstance(result, dict):
                    if 'usage' in result:
                        usage = result['usage']
                        timer.record_tokens(
                            'llm',
                            usage.get('prompt_tokens', 0),
                            usage.get('completion_tokens', 0)
                        )
                        metadata['tokens'] = usage.get('total_tokens', 0)

                timer.record_timing(timer_name, duration_ms, metadata)

                return result
            finally:
                if timer_name in timer.current_path:
                    timer.current_path.remove(timer_name)

        return async_wrapper
    return decorator


def get_current_timer() -> Optional[PerformanceTimer]:
    """获取当前请求的计时器"""
    metrics = current_metrics.get()
    if metrics is None:
        return None
    return metrics.get('timer')


def set_current_timer(timer: Optional[PerformanceTimer]):
    """设置当前请求的计时器"""
    current_metrics.set({'timer': timer})


class PerformanceContext:
    """性能监控上下文 - 用于整个请求生命周期"""

    def __init__(self):
        self.timer = PerformanceTimer()
        self.token = None

    def __enter__(self):
        self.token = current_metrics.set({'timer': self.timer})
        return self.timer

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.token:
            current_metrics.reset(self.token)
        return False

    async def __aenter__(self):
        return self.__enter__()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return self.__exit__(exc_type, exc_val, exc_tb)
