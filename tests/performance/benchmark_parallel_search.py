#!/usr/bin/env python3
"""
并行搜索性能基准测试

对比并行 vs 串行搜索的实际性能
"""

import asyncio
import sys
import time
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from tools.music_tools import MusicSearchTool


async def benchmark_search(query: str, parallel: bool, iterations: int = 3):
    """
    基准测试搜索性能

    Args:
        query: 搜索查询
        parallel: 是否并行搜索
        iterations: 迭代次数

    Returns:
        平均耗时（毫秒）
    """
    tool = MusicSearchTool()
    elapsed_times = []

    for i in range(iterations):
        print(f"\n{'='*60}")
        print(f"测试 #{i+1}: {'并行' if parallel else '串行'}搜索 - '{query}'")
        print(f"{'='*60}")

        start = time.time()
        result = await tool.search_songs_with_steps(
            query=query,
            limit=5,
            parallel=parallel
        )
        elapsed = (time.time() - start) * 1000
        elapsed_times.append(elapsed)

        print(f"\n✅ 搜索完成:")
        print(f"  - 来源: {result['source']}")
        print(f"  - 结果数: {len(result['songs'])}")
        print(f"  - 耗时: {elapsed:.0f}ms")

        if result['songs']:
            print(f"\n前 3 首歌曲:")
            for i, song in enumerate(result['songs'][:3], 1):
                print(f"  {i}. {song.title} - {song.artist}")

    avg_elapsed = sum(elapsed_times) / len(elapsed_times)
    return avg_elapsed


async def main():
    """主函数"""
    print("="*60)
    print("并行搜索性能基准测试")
    print("="*60)

    # 测试查询
    queries = [
        "Shape of You",  # RAG 应该能找到（高相似度）
        "Blinding Lights",  # 可能需要 Spotify
        "未知歌曲测试",  # 可能需要 TailyAPI 或本地数据库
    ]

    for query in queries:
        print(f"\n\n{'#'*60}")
        print(f"查询: {query}")
        print(f"{'#'*60}")

        # 并行搜索
        parallel_avg = await benchmark_search(query, parallel=True, iterations=2)

        # 串行搜索
        serial_avg = await benchmark_search(query, parallel=False, iterations=2)

        # 性能对比
        print(f"\n{'='*60}")
        print(f"性能对比 - '{query}':")
        print(f"  并行搜索平均耗时: {parallel_avg:.0f}ms")
        print(f"  串行搜索平均耗时: {serial_avg:.0f}ms")

        if parallel_avg < serial_avg:
            speedup = serial_avg / parallel_avg
            print(f"  性能提升: {speedup:.1f}x (并行更快)")
        else:
            slowdown = parallel_avg / serial_avg
            print(f"  性能下降: {slowdown:.1f}x (串行更快)")
        print(f"{'='*60}")


if __name__ == "__main__":
    asyncio.run(main())
