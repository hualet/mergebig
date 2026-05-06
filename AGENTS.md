# MergeBig 开发规范

## 项目定位

面向 Linux 用户的极简 TUI 大文件管理工具。核心原则：**简单、安全、高效**。

## 技术栈

- Python 3.8+（仅使用标准库，零第三方依赖）
- TUI 基于 `curses` 标准库实现
- 依赖管理：`uv venv` + `pyproject.toml`
- 代码规范：`ruff`（lint + format）

## 代码规范

- 缩进使用 4 个空格，禁止 tab
- 行长度限制 100 字符
- 引号使用双引号
- 换行符使用 LF
- 提交前运行：`ruff check mergebig/ && ruff format mergebig/`

## 代码规范

- 所有路径操作使用 `pathlib.Path`
- 字符串格式化使用 f-string
- 类型注解可选但鼓励使用
- 异常处理要具体（`OSError`, `PermissionError` 等），不裸 `except`

## 文件结构

```
mergebig/
    __init__.py      # 版本信息
    __main__.py      # python -m mergebig 入口
    cli.py           # 命令行参数解析
    scanner.py       # 文件扫描、hash 计算
    core.py          # 重复检测、合并逻辑
    tui.py           # curses TUI 界面
```

## 核心逻辑约束

1. **大文件阈值**：默认 100MB，命令行通过 `--min-size` 调整，支持 `M`/`G` 后缀
2. **Hash 策略**：
   - 第一层：按文件大小分组
   - 第二层：大小相同文件计算快速 hash（前 4KB）
   - 第三层：快速 hash 相同文件计算完整 SHA256
3. **合并策略**：
   - 重复文件：通过完整 SHA256 确认相同后，保留一个，其他用 hardlink 指向它
   - 同名文件：文件名完全匹配 + 完整 SHA256 相同，才允许 hardlink 合并
   - hardlink 使用 `os.link(src, dst)`，先删除 dst 再创建链接
4. **删除策略**：
   - 必须有用户明确确认（TUI 中选中后按 Enter）
   - 删除前再次显示文件路径和大小

## TUI 设计

- 极简风格，不使用颜色或仅使用基本高亮
- 三栏布局：左侧功能列表，中间文件列表，右侧详情/预览
- 状态栏显示当前操作和统计信息
- 支持键盘导航，也显示快捷键提示

## 测试

- 在 `/tmp` 下创建测试目录和文件进行验证
- 测试场景：空目录、无大文件、有重复文件、有同名文件、跨目录 hardlink
