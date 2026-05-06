"""命令行参数解析"""

import argparse
from pathlib import Path


def parse_size(size_str: str) -> int:
    """解析大小字符串，如 '100M', '1G' -> 字节数"""
    size_str = size_str.strip().upper()
    multipliers = {
        "K": 1024,
        "M": 1024**2,
        "G": 1024**3,
        "T": 1024**4,
    }

    for suffix, mult in multipliers.items():
        if size_str.endswith(suffix):
            return int(float(size_str[:-1]) * mult)

    return int(size_str)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="mergebig", description="大文件查找/清理、重复大文件查找/合并工具"
    )
    parser.add_argument(
        "path", nargs="?", default=".", help="扫描路径 (默认: 当前目录)"
    )
    parser.add_argument(
        "--min-size", default="100M", help="大文件阈值，支持 M/G 后缀 (默认: 100M)"
    )
    parser.add_argument(
        "--skip",
        default=".git,node_modules,__pycache__,.venv,venv,target",
        help="跳过的目录名，逗号分隔",
    )
    return parser.parse_args()


def get_config() -> dict:
    args = parse_args()
    skip_dirs = set(d.strip() for d in args.skip.split(",") if d.strip())
    return {
        "path": Path(args.path).resolve(),
        "min_size": parse_size(args.min_size),
        "skip_dirs": skip_dirs,
    }
