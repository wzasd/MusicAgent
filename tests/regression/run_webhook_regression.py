#!/usr/bin/env python3
"""
Webhook 回归测试运行脚本

用法:
    python run_webhook_regression.py [选项]

选项:
    --quick       只运行直接歌曲搜索测试（较快）
    --lyrics      只运行歌词搜索测试
    --all         运行所有测试（默认）
    --report      生成详细报告
"""

import sys
import subprocess
import argparse


def main():
    parser = argparse.ArgumentParser(description="运行 Webhook 回归测试")
    parser.add_argument(
        "--quick",
        action="store_true",
        help="只运行直接歌曲搜索测试（较快）"
    )
    parser.add_argument(
        "--lyrics",
        action="store_true",
        help="只运行歌词搜索测试"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="运行所有测试（默认）"
    )
    parser.add_argument(
        "--batch",
        action="store_true",
        help="运行批量测试（生成完整报告）"
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="详细输出"
    )

    args = parser.parse_args()

    # 构建 pytest 命令
    pytest_args = ["python", "-m", "pytest", "tests/regression/test_webhook_regression.py"]

    if args.verbose:
        pytest_args.extend(["-v", "-s"])

    # 选择测试
    if args.quick:
        pytest_args.extend(["-k", "test_direct_song"])
    elif args.lyrics:
        pytest_args.extend(["-k", "test_lyrics"])
    elif args.batch:
        pytest_args.extend(["-k", "test_batch"])
    else:
        # 默认运行所有
        pytest_args.extend(["-m", "webhook"])

    print("="*70)
    print("Webhook 回归测试")
    print("="*70)
    print(f"运行命令: {' '.join(pytest_args)}")
    print()

    # 运行测试
    result = subprocess.run(pytest_args)

    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
