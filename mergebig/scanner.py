"""文件扫描与 hash 计算"""

import os
import hashlib
from pathlib import Path
from collections import defaultdict
from typing import List, Dict, Optional


def format_size(size_bytes: int) -> str:
    """格式化文件大小显示"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if abs(size_bytes) < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} PB"


def quick_hash(filepath: Path, chunk_size: int = 4096) -> Optional[str]:
    """计算文件前 chunk_size 字节的 hash"""
    try:
        hasher = hashlib.sha256()
        with open(filepath, 'rb') as f:
            data = f.read(chunk_size)
            hasher.update(data)
            hasher.update(str(filepath.stat().st_size).encode())
        return hasher.hexdigest()
    except (OSError, IOError):
        return None


def full_hash(filepath: Path, chunk_size: int = 65536) -> Optional[str]:
    """计算文件完整 SHA256 hash"""
    try:
        hasher = hashlib.sha256()
        with open(filepath, 'rb') as f:
            while chunk := f.read(chunk_size):
                hasher.update(chunk)
        return hasher.hexdigest()
    except (OSError, IOError):
        return None


class FileInfo:
    """文件信息对象"""
    def __init__(self, path: Path):
        self.path = path
        self.name = path.name
        stat = path.stat()
        self.size = stat.st_size
        self.quick_hash: Optional[str] = None
        self.full_hash: Optional[str] = None
    
    def __repr__(self):
        return f"FileInfo({self.path}, {format_size(self.size)})"


def scan_large_files(root_dir: Path, min_size: int, skip_dirs: set) -> List[FileInfo]:
    """扫描目录查找大文件"""
    results = []
    for root, dirs, files in os.walk(root_dir):
        # 跳过指定目录
        dirs[:] = [d for d in dirs if d not in skip_dirs and not d.startswith('.')]
        
        for filename in files:
            filepath = Path(root) / filename
            try:
                size = filepath.stat().st_size
                if size >= min_size:
                    results.append(FileInfo(filepath))
            except (OSError, IOError):
                continue
    
    return results


def group_by_size(files: List[FileInfo]) -> Dict[int, List[FileInfo]]:
    """按大小分组"""
    groups = defaultdict(list)
    for f in files:
        groups[f.size].append(f)
    return groups


def find_duplicates_by_hash(files: List[FileInfo]) -> List[List[FileInfo]]:
    """通过 hash 查找重复文件，返回文件组列表"""
    # 第一层：按大小分组
    size_groups = group_by_size(files)
    
    candidates = []
    for size, group in size_groups.items():
        if len(group) > 1:
            candidates.extend(group)
    
    if not candidates:
        return []
    
    # 第二层：快速 hash
    quick_groups = defaultdict(list)
    for f in candidates:
        f.quick_hash = quick_hash(f.path)
        if f.quick_hash:
            quick_groups[f.quick_hash].append(f)
    
    # 第三层：完整 hash
    full_groups = defaultdict(list)
    for qhash, group in quick_groups.items():
        if len(group) > 1:
            for f in group:
                f.full_hash = full_hash(f.path)
                if f.full_hash:
                    full_groups[f.full_hash].append(f)
    
    # 返回重复组
    return [group for group in full_groups.values() if len(group) > 1]


def find_duplicates_by_name(files: List[FileInfo]) -> List[List[FileInfo]]:
    """通过文件名查找同名文件，返回文件组列表（按 hash 验证是否相同）"""
    name_groups = defaultdict(list)
    for f in files:
        name_groups[f.name].append(f)
    
    # 只保留同名且数量大于1的组
    candidates = []
    for group in name_groups.values():
        if len(group) > 1:
            candidates.extend(group)
    
    if not candidates:
        return []
    
    # 计算完整 hash 并按 hash 分组
    hash_groups = defaultdict(list)
    for f in candidates:
        f.full_hash = full_hash(f.path)
        if f.full_hash:
            hash_groups[f.full_hash].append(f)
    
    return [group for group in hash_groups.values() if len(group) > 1]
