"""核心逻辑：合并、删除等操作"""

import os
from pathlib import Path
from typing import List
from .scanner import FileInfo, format_size


def delete_files(files: List[FileInfo]) -> tuple:
    """删除文件，返回 (成功数, 失败列表)"""
    success = 0
    failed = []
    for f in files:
        try:
            f.path.unlink()
            success += 1
        except (OSError, PermissionError) as e:
            failed.append((f, str(e)))
    return success, failed


def hardlink_files(file_groups: List[List[FileInfo]], keep_first: bool = True) -> tuple:
    """将重复文件用 hardlink 合并，返回 (成功组数, 失败列表)
    
    每组保留第一个文件作为 master，其他文件删除后重新创建 hardlink
    """
    success_groups = 0
    failed = []
    
    for group in file_groups:
        if len(group) < 2:
            continue
        
        # 按路径排序，确保确定性
        group_sorted = sorted(group, key=lambda f: str(f.path))
        master = group_sorted[0]
        
        group_success = True
        for f in group_sorted[1:]:
            try:
                # 确保在同一文件系统
                if f.path.stat().st_dev != master.path.stat().st_dev:
                    failed.append((f, "与 master 不在同一文件系统，无法 hardlink"))
                    group_success = False
                    continue
                
                # 删除目标文件，然后创建 hardlink
                f.path.unlink()
                os.link(master.path, f.path)
            except (OSError, PermissionError) as e:
                failed.append((f, str(e)))
                group_success = False
        
        if group_success:
            success_groups += 1
    
    return success_groups, failed


def calculate_wasted_space(file_groups: List[List[FileInfo]]) -> int:
    """计算重复文件浪费的空间"""
    wasted = 0
    for group in file_groups:
        if len(group) > 1:
            wasted += group[0].size * (len(group) - 1)
    return wasted
