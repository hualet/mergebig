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


def save_html_report(report, output_file):
    """保存报告为 HTML 网页"""
    # 准备数据
    summary = report['summary']
    total_size_formatted = format_size(summary['total_size'])
    wasted_space_formatted = format_size(summary['wasted_space'])

    # 构建 HTML 内容
    html_content = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>大文件重复情况分析报告</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px;
            line-height: 1.6;
        }}

        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 16px;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
            overflow: hidden;
        }}

        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 40px;
            text-align: center;
        }}

        .header h1 {{
            font-size: 2.5em;
            margin-bottom: 10px;
            font-weight: 700;
        }}

        .header .meta {{
            opacity: 0.9;
            font-size: 0.95em;
            margin-top: 15px;
        }}

        .summary {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            padding: 40px;
            background: #f8f9fa;
        }}

        .stat-card {{
            background: white;
            padding: 25px;
            border-radius: 12px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05);
            text-align: center;
            transition: transform 0.2s, box-shadow 0.2s;
        }}

        .stat-card:hover {{
            transform: translateY(-5px);
            box-shadow: 0 8px 15px rgba(0, 0, 0, 0.1);
        }}

        .stat-card .label {{
            color: #6c757d;
            font-size: 0.9em;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 10px;
        }}

        .stat-card .value {{
            font-size: 2em;
            font-weight: 700;
            color: #667eea;
        }}

        .stat-card.wasted .value {{
            color: #e74c3c;
        }}

        .section {{
            padding: 40px;
        }}

        .section-title {{
            font-size: 1.8em;
            color: #2c3e50;
            margin-bottom: 25px;
            padding-bottom: 15px;
            border-bottom: 3px solid #667eea;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }}

        .toggle-btn {{
            background: #667eea;
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 0.9em;
            transition: background 0.2s;
        }}

        .toggle-btn:hover {{
            background: #5568d3;
        }}

        .duplicate-group {{
            background: #f8f9fa;
            border-radius: 12px;
            margin-bottom: 20px;
            overflow: hidden;
            transition: box-shadow 0.2s;
        }}

        .duplicate-group:hover {{
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
        }}

        .duplicate-header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            cursor: pointer;
            display: flex;
            justify-content: space-between;
            align-items: center;
            user-select: none;
        }}

        .duplicate-header:hover {{
            opacity: 0.95;
        }}

        .duplicate-info {{
            display: flex;
            gap: 30px;
            align-items: center;
            flex-wrap: wrap;
        }}

        .duplicate-info .info-item {{
            display: flex;
            flex-direction: column;
        }}

        .duplicate-info .info-label {{
            font-size: 0.8em;
            opacity: 0.9;
            text-transform: uppercase;
        }}

        .duplicate-info .info-value {{
            font-size: 1.3em;
            font-weight: 600;
        }}

        .toggle-icon {{
            font-size: 1.5em;
            transition: transform 0.3s;
        }}

        .toggle-icon.expanded {{
            transform: rotate(180deg);
        }}

        .file-list {{
            max-height: 0;
            overflow: hidden;
            transition: max-height 0.3s ease-out;
        }}

        .file-list.expanded {{
            max-height: 2000px;
        }}

        .file-item {{
            padding: 15px 20px;
            border-bottom: 1px solid #e9ecef;
            display: flex;
            align-items: center;
            gap: 15px;
        }}

        .file-item:last-child {{
            border-bottom: none;
        }}

        .file-icon {{
            color: #667eea;
            font-size: 1.5em;
        }}

        .file-path {{
            flex: 1;
            font-family: "Courier New", monospace;
            font-size: 0.95em;
            color: #495057;
            word-break: break-all;
        }}

        .file-size {{
            color: #6c757d;
            font-size: 0.9em;
            white-space: nowrap;
        }}

        .empty-state {{
            text-align: center;
            padding: 60px 20px;
            color: #6c757d;
        }}

        .empty-state .icon {{
            font-size: 4em;
            margin-bottom: 20px;
            opacity: 0.5;
        }}

        .empty-state p {{
            font-size: 1.2em;
        }}

        .large-files-section {{
            background: #f8f9fa;
        }}

        .large-file-item {{
            background: white;
            padding: 15px 20px;
            border-radius: 8px;
            margin-bottom: 10px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            transition: box-shadow 0.2s;
        }}

        .large-file-item:hover {{
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
        }}

        .large-file-path {{
            flex: 1;
            font-family: "Courier New", monospace;
            color: #495057;
            word-break: break-all;
            margin-right: 20px;
        }}

        .large-file-size {{
            color: #667eea;
            font-weight: 600;
            white-space: nowrap;
        }}

        @media (max-width: 768px) {{
            .summary {{
                grid-template-columns: 1fr;
            }}

            .header h1 {{
                font-size: 1.8em;
            }}

            .duplicate-info {{
                gap: 15px;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>大文件重复情况分析报告</h1>
            <div class="meta">
                <p>扫描时间: {report['scan_time']}</p>
                <p>扫描目录: {report['scan_directory']}</p>
                <p>最小文件大小: {report['min_file_size_formatted']}</p>
            </div>
        </div>

        <div class="summary">
            <div class="stat-card">
                <div class="label">大文件总数</div>
                <div class="value">{summary['total_large_files']}</div>
            </div>
            <div class="stat-card">
                <div class="label">大文件总大小</div>
                <div class="value">{total_size_formatted}</div>
            </div>
            <div class="stat-card">
                <div class="label">重复文件组</div>
                <div class="value">{summary['duplicate_hash_groups']}</div>
            </div>
            <div class="stat-card wasted">
                <div class="label">可节省空间</div>
                <div class="value">{wasted_space_formatted}</div>
            </div>
        </div>

        <div class="section">
            <div class="section-title">
                <span>重复文件详情</span>
                <button class="toggle-btn" onclick="toggleAll()">展开/收起全部</button>
            </div>
            <div id="duplicates-container">
'''

    # 添加重复文件详情
    if report['duplicate_details']:
        for idx, dup in enumerate(report['duplicate_details']):
            size_formatted = format_size(dup['size'])
            wasted_formatted = format_size(dup['wasted_space'])
            hash_short = dup['hash'][:16] + '...'

            html_content += f'''
                <div class="duplicate-group">
                    <div class="duplicate-header" onclick="toggleGroup({idx})">
                        <div class="duplicate-info">
                            <div class="info-item">
                                <span class="info-label">文件大小</span>
                                <span class="info-value">{size_formatted}</span>
                            </div>
                            <div class="info-item">
                                <span class="info-label">重复次数</span>
                                <span class="info-value">{dup['count']}</span>
                            </div>
                            <div class="info-item">
                                <span class="info-label">浪费空间</span>
                                <span class="info-value">{wasted_formatted}</span>
                            </div>
                        </div>
                        <span class="toggle-icon" id="icon-{idx}">▼</span>
                    </div>
                    <div class="file-list" id="list-{idx}">
'''

            for file_info in dup['files']:
                file_size_formatted = format_size(file_info['size'])
                html_content += f'''
                        <div class="file-item">
                            <span class="file-icon">📄</span>
                            <span class="file-path">{file_info['path']}</span>
                            <span class="file-size">{file_size_formatted}</span>
                        </div>
'''

            html_content += f'''
                    </div>
                </div>
'''
    else:
        html_content += '''
                <div class="empty-state">
                    <div class="icon">✓</div>
                    <p>未发现重复文件</p>
                </div>
'''

    html_content += f'''
            </div>
        </div>

        <div class="section large-files-section">
            <div class="section-title">
                <span>前20个大文件</span>
            </div>
            <div id="large-files-container">
'''

    # 添加大文件列表
    for file_info in report['large_files'][:20]:
        file_size_formatted = format_size(file_info['size'])
        html_content += f'''
                <div class="large-file-item">
                    <span class="large-file-path">{file_info['path']}</span>
                    <span class="large-file-size">{file_size_formatted}</span>
                </div>
'''

    html_content += '''
            </div>
        </div>
    </div>

    <script>
        function toggleGroup(idx) {
            const list = document.getElementById('list-' + idx);
            const icon = document.getElementById('icon-' + idx);

            if (list.classList.contains('expanded')) {
                list.classList.remove('expanded');
                icon.classList.remove('expanded');
            } else {
                list.classList.add('expanded');
                icon.classList.add('expanded');
            }
        }

        function toggleAll() {
            const lists = document.querySelectorAll('.file-list');
            const icons = document.querySelectorAll('.toggle-icon');
            const allExpanded = Array.from(lists).every(list => list.classList.contains('expanded'));

            lists.forEach(list => {
                if (allExpanded) {
                    list.classList.remove('expanded');
                } else {
                    list.classList.add('expanded');
                }
            });

            icons.forEach(icon => {
                if (allExpanded) {
                    icon.classList.remove('expanded');
                } else {
                    icon.classList.add('expanded');
                }
            });
        }
    </script>
</body>
</html>
'''

    # 写入文件
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html_content)

    print(f"HTML 报告已保存到: {output_file}")


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
    output_file = Path(__file__).parent / "duplicate_files_report.html"
    save_html_report(report, output_file)

    elapsed_time = time.time() - start_time
    print(f"\n分析完成！耗时: {elapsed_time:.2f} 秒")


if __name__ == "__main__":
    main()
