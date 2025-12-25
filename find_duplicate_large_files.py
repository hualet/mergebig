#!/usr/bin/env python3
"""查找大文件并分析重复情况的脚本"""

import os
import hashlib
from pathlib import Path
from collections import defaultdict
import json
import time
from datetime import datetime
from copy import deepcopy


MIN_SIZE = 50 * 1024 * 1024  # 50MB
HOME_DIR = Path.home()


def calculate_file_hash(filepath, chunk_size=8192):
    """计算文件的 SHA256 hash"""
    hasher = hashlib.sha256()
    try:
        with open(filepath, 'rb') as f:
            while chunk := f.read(chunk_size):
                hasher.update(chunk)
        return hasher.hexdigest()
    except (OSError, IOError) as e:
        return None


def format_size(size_bytes):
    """格式化文件大小显示"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} PB"


def scan_large_files(root_dir, min_size):
    """扫描目录查找大文件"""
    print(f"正在扫描目录: {root_dir}")
    print(f"查找大于 {format_size(min_size)} 的文件...")
    large_files = []
    total_files = 0

    for root, dirs, files in os.walk(root_dir):
        # 跳过隐藏目录和常见缓存目录
        dirs[:] = [d for d in dirs if not d.startswith('.') and d not in [
            'node_modules', '__pycache__'
        ]]

        for filename in files:
            filepath = Path(root) / filename
            total_files += 1

            try:
                size = filepath.stat().st_size
                if size >= min_size:
                    large_files.append({
                        'path': str(filepath),
                        'name': filename,
                        'size': size,
                    })
                    if len(large_files) % 10 == 0:
                        print(f"  已找到 {len(large_files)} 个大文件...")
            except (OSError, IOError):
                continue

    print(f"扫描完成！共检查 {total_files} 个文件，找到 {len(large_files)} 个大文件\n")
    return large_files


def find_duplicates(large_files):
    """查找重复文件（按文件名和 hash）"""
    print("正在分析重复文件...")

    # 按文件名分组
    files_by_name = defaultdict(list)
    for file_info in large_files:
        files_by_name[file_info['name']].append(file_info)

    # 找出重名的文件组
    duplicate_names = {
        name: files for name, files in files_by_name.items() if len(files) > 1
    }

    print(f"找到 {len(duplicate_names)} 组重名文件")
    print("正在计算文件 hash 以验证是否为相同文件...")

    # 统计需要计算 hash 的文件总数
    total_to_hash = sum(len(files) for files in duplicate_names.values())
    processed = 0

    # 计算每个文件的 hash 并按 hash 分组
    duplicates_by_hash = defaultdict(list)

    for name, files in duplicate_names.items():
        print(f"  [{processed + 1}/{total_to_hash}] 分析文件: {name} ({len(files)} 个副本)")
        for file_info in files:
            filepath = file_info['path']
            file_hash = calculate_file_hash(filepath)
            processed += 1
            if file_hash:
                file_info['hash'] = file_hash
                duplicates_by_hash[file_hash].append(file_info)
            else:
                print(f"    警告: 无法读取文件 {filepath}")

    # 找出真正重复的文件（hash 相同）
    true_duplicates = {
        h: files for h, files in duplicates_by_hash.items() if len(files) > 1
    }

    print(f"\n验证完成！找到 {len(true_duplicates)} 组真正重复的文件\n")
    return {
        'by_name': duplicate_names,
        'by_hash': true_duplicates
    }


def generate_report(large_files, duplicates):
    """生成分析报告"""
    # 计算浪费的空间和重复文件详情
    wasted_space = 0
    duplicate_details = []

    for file_hash, files in duplicates['by_hash'].items():
        file_count = len(files)
        file_size = files[0]['size']
        wasted = file_size * (file_count - 1)
        wasted_space += wasted

        duplicate_details.append({
            'hash': file_hash,
            'size': file_size,
            'count': file_count,
            'wasted_space': wasted,
            'files': [{'path': f['path'], 'size': f['size']} for f in files]
        })

    duplicate_details.sort(key=lambda x: x['wasted_space'], reverse=True)

    report = {
        'scan_time': datetime.now().isoformat(),
        'scan_directory': str(HOME_DIR),
        'min_file_size': MIN_SIZE,
        'min_file_size_formatted': format_size(MIN_SIZE),
        'summary': {
            'total_large_files': len(large_files),
            'total_size': sum(f['size'] for f in large_files),
            'duplicate_name_groups': len(duplicates['by_name']),
            'duplicate_hash_groups': len(duplicates['by_hash']),
            'wasted_space': wasted_space,
        },
        'large_files': sorted(large_files, key=lambda x: x['size'], reverse=True)[:20],
        'duplicate_details': duplicate_details,
    }

    return report


def print_report(report):
    """打印可读的报告"""
    print("=" * 80)
    print("大文件重复情况分析报告")
    print("=" * 80)
    print(f"扫描时间: {report['scan_time']}")
    print(f"扫描目录: {report['scan_directory']}")
    print(f"最小文件大小: {report['min_file_size_formatted']}")
    print()

    print("-" * 80)
    print("总体统计")
    print("-" * 80)
    print(f"大文件总数: {report['summary']['total_large_files']}")
    print(f"大文件总大小: {format_size(report['summary']['total_size'])}")
    print(f"重名文件组: {report['summary']['duplicate_name_groups']}")
    print(f"重复文件组 (hash相同): {report['summary']['duplicate_hash_groups']}")
    print(f"可节省空间: {format_size(report['summary']['wasted_space'])}")
    print()

    if report['duplicate_details']:
        print("-" * 80)
        print("重复文件详情 (按浪费空间排序)")
        print("-" * 80)

        for i, dup in enumerate(report['duplicate_details'], 1):
            print(f"\n[{i}] 文件大小: {format_size(dup['size'])}, "
                  f"重复次数: {dup['count']}, "
                  f"浪费空间: {format_size(dup['wasted_space'])}")
            for f in dup['files']:
                print(f"    - {f['path']}")

    print()
    print("=" * 80)


def save_report(report, output_file):
    """保存报告到 JSON 文件"""
    # 使用深拷贝避免修改原始报告
    report_copy = deepcopy(report)

    # 添加格式化的大小字段
    report_copy['summary']['total_size_formatted'] = format_size(report['summary']['total_size'])
    report_copy['summary']['wasted_space_formatted'] = format_size(report['summary']['wasted_space'])

    for dup in report_copy['duplicate_details']:
        dup['size_formatted'] = format_size(dup['size'])
        dup['wasted_space_formatted'] = format_size(dup['wasted_space'])

    for f in report_copy['large_files']:
        f['size_formatted'] = format_size(f['size'])

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(report_copy, f, ensure_ascii=False, indent=2)

    print(f"详细报告已保存到: {output_file}")


def main():
    print("=" * 80)
    print("大文件重复情况查找工具")
    print("=" * 80)
    print()

    start_time = time.time()

    # 步骤1: 扫描大文件
    large_files = scan_large_files(HOME_DIR, MIN_SIZE)

    if not large_files:
        print("未找到大文件，程序结束。")
        return

    # 步骤2: 查找重复
    duplicates = find_duplicates(large_files)

    # 步骤3: 生成报告
    report = generate_report(large_files, duplicates)

    # 步骤4: 打印报告
    print_report(report)

    # 步骤5: 保存报告
    output_file = Path(__file__).parent / "duplicate_files_report.json"
    save_report(report, output_file)

    elapsed_time = time.time() - start_time
    print(f"\n分析完成！耗时: {elapsed_time:.2f} 秒")


if __name__ == "__main__":
    main()
