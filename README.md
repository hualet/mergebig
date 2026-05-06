# MergeBig

面向 Linux 用户的大文件管理工具，提供极简 TUI 界面。

## 功能

- **大文件查找/清理**：扫描指定目录，列出超过阈值的大文件，支持交互式删除
- **重复大文件查找/合并**：通过文件 hash 判断重复，使用 hardlink 合并以节省空间
- **同名大文件查找/合并**：按文件名完全匹配，使用 hardlink 合并相同文件

## 安装

```bash
# 克隆仓库
git clone <repo-url>
cd mergebig

# 创建 uv 虚拟环境并安装
uv venv
uv pip install -e .

# 运行
python -m mergebig
```

## 使用

```bash
# 启动 TUI（默认扫描当前目录，阈值 100MB）
python -m mergebig

# 指定扫描目录和阈值
python -m mergebig /home/user/data --min-size 50M

# 跳过目录（逗号分隔）
python -m mergebig --skip .git,node_modules,__pycache__
```

### 命令行参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `PATH` | 扫描路径 | `.` |
| `--min-size` | 大文件阈值（支持 M/G 后缀） | `100M` |
| `--skip` | 跳过的目录名（逗号分隔） | `.git,node_modules,__pycache__,.venv` |

### TUI 操作

| 按键 | 功能 |
|------|------|
| `↑/↓` 或 `k/j` | 移动光标 |
| `Space` | 选中/取消选中 |
| `a` | 全选/取消全选 |
| `Enter` | 执行操作（删除/合并） |
| `q` | 退出 |
| `Tab` | 切换功能页 |

## 技术细节

- **重复文件检测**：先按大小分组，再计算快速 hash（前 4KB），最后计算完整 SHA256
- **合并方式**：使用 `os.link()` 创建 hardlink，不占用额外磁盘空间
- **安全性**：合并前校验 hash，只合并完全相同的文件；hardlink 后各路径共享同一 inode

## License

MIT
