"""极简 TUI 界面（基于 curses）"""

import curses
import time
from typing import List
from .scanner import (
    FileInfo,
    format_size,
    scan_large_files,
    find_duplicates_by_hash,
    find_duplicates_by_name,
)
from .core import delete_files, hardlink_files, calculate_wasted_space


class TUI:
    MODES = [
        ("large", "大文件"),
        ("dup_hash", "重复文件"),
        ("dup_name", "同名文件"),
    ]

    def __init__(self, config: dict):
        self.config = config
        self.mode_idx = 0
        self.files: List[FileInfo] = []
        self.groups: List[List[FileInfo]] = []
        self._group_cache: dict = {}
        self.selected: set = set()
        self.cursor = 0
        self.scroll_top = 0
        self.message = ""
        self.message_color = 0
        self.scanning = True

    def run(self):
        curses.wrapper(self._main)

    def _main(self, stdscr):
        self.stdscr = stdscr
        curses.curs_set(0)
        stdscr.timeout(100)

        # 初始化颜色
        if curses.has_colors():
            curses.start_color()
            curses.use_default_colors()
            curses.init_pair(1, curses.COLOR_CYAN, -1)
            curses.init_pair(2, curses.COLOR_GREEN, -1)
            curses.init_pair(3, curses.COLOR_YELLOW, -1)
            curses.init_pair(4, curses.COLOR_RED, -1)

        # 阶段1: 扫描，显示进度
        self._scan()
        self.scanning = False

        # 进入交互主界面后恢复阻塞输入，避免无输入时持续刷新
        stdscr.timeout(-1)

        # 阶段2: 交互主界面
        while True:
            self._draw()
            key = stdscr.getch()

            if key == ord("q") or key == 27:
                break
            elif key == curses.KEY_UP or key == ord("k"):
                self._move_cursor(-1)
            elif key == curses.KEY_DOWN or key == ord("j"):
                self._move_cursor(1)
            elif key == curses.KEY_PPAGE:
                self._move_cursor(-10)
            elif key == curses.KEY_NPAGE:
                self._move_cursor(10)
            elif key == ord(" "):
                self._toggle_select()
            elif key == ord("a"):
                self._toggle_select_all()
            elif key == ord("\n") or key == ord("\r"):
                self._execute()
            elif key == ord("\t") or key == curses.KEY_RIGHT:
                self._next_mode()
            elif key == curses.KEY_LEFT:
                self._prev_mode()

    def _scan(self):
        """扫描文件，带进度显示"""
        self.scanning = True
        self.scan_progress = {
            "dirs_scanned": 0,
            "files_checked": 0,
            "large_files_found": 0,
            "current_dir": str(self.config["path"]),
        }

        # 先显示一次进度界面
        self._draw_scan_progress()
        last_draw = time.monotonic()

        def on_progress(stats):
            nonlocal last_draw
            self.scan_progress = stats
            now = time.monotonic()
            if now - last_draw >= 0.1:  # 限制刷新频率，至少间隔 100ms
                last_draw = now
                self._draw_scan_progress()

        self.files = scan_large_files(
            self.config["path"],
            self.config["min_size"],
            self.config["skip_dirs"],
            progress_callback=on_progress,
        )

        # 扫描结束后再刷新一次，确保显示最终结果
        self._draw_scan_progress()

        self.scanning = False
        # 预先计算所有模式的分组，避免切换标签页时重复计算导致卡顿
        self._precompute_all_groups()
        self._refresh_groups()

    def _draw_scan_progress(self):
        """绘制扫描进度界面"""
        stdscr = self.stdscr
        h, w = stdscr.getmaxyx()
        stdscr.clear()

        if h < 10 or w < 40:
            self._safe_addstr(0, 0, "窗口太小")
            stdscr.refresh()
            return

        # 标题
        title = " MergeBig - 正在扫描 "
        self._safe_addstr(1, max(0, (w - len(title)) // 2), title, curses.A_BOLD)

        # 分隔线
        self._safe_addstr(3, 0, "─" * (w - 1))

        stats = self.scan_progress
        lines = [
            "",
            f"  扫描目录: {stats['dirs_scanned']}",
            f"  检查文件: {stats['files_checked']}",
            f"  发现大文件: {stats['large_files_found']}",
            "",
            f"  当前: {stats['current_dir'][-w + 10 :]}",
            "",
            "  请稍候...",
        ]

        y = 5
        for line in lines:
            self._safe_addstr(y, 0, line)
            y += 1

        stdscr.refresh()

    def _precompute_all_groups(self):
        """预先计算所有三种模式的分组数据，避免切换标签页时卡顿"""
        self._group_cache = {
            "large": [[f] for f in self.files],
            "dup_hash": find_duplicates_by_hash(self.files),
            "dup_name": find_duplicates_by_name(self.files),
        }

    def _refresh_groups(self):
        """根据当前模式刷新分组（从预计算缓存读取）"""
        mode = self.MODES[self.mode_idx][0]
        self.groups = self._group_cache.get(mode, [])

        self.selected.clear()
        self.cursor = 0
        self.scroll_top = 0

        mode_name = self.MODES[self.mode_idx][1]
        total = sum(len(g) for g in self.groups)
        if mode == "large":
            self.message = f"{mode_name}: {total} 个文件"
        else:
            self.message = f"{mode_name}: {len(self.groups)} 组, {total} 个文件"
        self.message_color = 2

    def _next_mode(self):
        self.mode_idx = (self.mode_idx + 1) % len(self.MODES)
        self._refresh_groups()

    def _prev_mode(self):
        self.mode_idx = (self.mode_idx - 1) % len(self.MODES)
        self._refresh_groups()

    def _get_flat_items(self):
        """将分组展平为列表，每组之间插入分隔"""
        items = []
        for i, group in enumerate(self.groups):
            if i > 0 and len(self.groups) > 1:
                items.append(("sep", None))
            for f in group:
                items.append(("file", f))
        return items

    def _move_cursor(self, delta: int):
        items = self._get_flat_items()
        if not items:
            return
        self.cursor = max(0, min(len(items) - 1, self.cursor + delta))

        # 调整滚动
        h = self.stdscr.getmaxyx()[0]
        list_height = h - 4  # 标题 + 模式栏 + 状态栏 + 边框
        if self.cursor < self.scroll_top:
            self.scroll_top = self.cursor
        elif self.cursor >= self.scroll_top + list_height:
            self.scroll_top = self.cursor - list_height + 1

    def _toggle_select(self):
        items = self._get_flat_items()
        if not items or self.cursor >= len(items):
            return
        item_type, item = items[self.cursor]
        if item_type != "file":
            return

        key = str(item.path)
        if key in self.selected:
            self.selected.remove(key)
        else:
            self.selected.add(key)

    def _toggle_select_all(self):
        items = self._get_flat_items()
        files = [str(f.path) for t, f in items if t == "file"]
        if not files:
            return

        all_selected = all(f in self.selected for f in files)
        if all_selected:
            for f in files:
                self.selected.discard(f)
        else:
            for f in files:
                self.selected.add(f)

    def _execute(self):
        mode = self.MODES[self.mode_idx][0]
        items = self._get_flat_items()
        selected_files = [
            f for t, f in items if t == "file" and str(f.path) in self.selected
        ]

        if not selected_files:
            self.message = "未选中任何文件"
            self.message_color = 4
            return

        if mode == "large":
            # 删除确认
            self.message = (
                f"确认删除 {len(selected_files)} 个文件? 按 Enter 确认，其他键取消"
            )
            self.message_color = 4
            self._draw()
            key = self.stdscr.getch()
            if key == ord("\n") or key == ord("\r"):
                success, failed = delete_files(selected_files)
                self.message = f"删除完成: {success} 成功, {len(failed)} 失败"
                self.message_color = 2 if not failed else 3
                # 重新扫描
                self._scan()
            else:
                self.message = "已取消"
                self.message_color = 3
        else:
            # 合并确认
            # 按 hash 分组筛选出完全选中的组
            selected_set = set(str(f.path) for f in selected_files)
            merge_groups = []
            for group in self.groups:
                # 只合并选中的文件，每组至少保留一个未选中的或自动处理
                selected_in_group = [f for f in group if str(f.path) in selected_set]
                if len(selected_in_group) >= 1:
                    # 找到 master（未选中的第一个，或选中的第一个）
                    unselected = [f for f in group if str(f.path) not in selected_set]
                    if unselected:
                        master = unselected[0]
                        merge_groups.append([master] + selected_in_group)
                    else:
                        # 整组都被选中，保留第一个
                        merge_groups.append(selected_in_group)

            if not merge_groups:
                self.message = "没有可合并的组"
                self.message_color = 4
                return

            total_wasted = calculate_wasted_space(merge_groups)
            self.message = f"确认合并 {len(merge_groups)} 组? 可节省 {format_size(total_wasted)} 按 Enter 确认"
            self.message_color = 4
            self._draw()
            key = self.stdscr.getch()
            if key == ord("\n") or key == ord("\r"):
                success, failed = hardlink_files(merge_groups)
                self.message = f"合并完成: {success} 组成功, {len(failed)} 失败"
                self.message_color = 2 if not failed else 3
                self._scan()
            else:
                self.message = "已取消"
                self.message_color = 3

    def _safe_addstr(self, y: int, x: int, text: str, attr=0):
        """安全地写入字符串，避免越界"""
        try:
            h, w = self.stdscr.getmaxyx()
            if y < 0 or y >= h or x < 0 or x >= w:
                return
            max_len = w - x
            if max_len <= 0:
                return
            if len(text) > max_len:
                text = text[:max_len]
            self.stdscr.addstr(y, x, text, attr)
        except curses.error:
            pass

    def _draw(self):
        stdscr = self.stdscr
        h, w = stdscr.getmaxyx()
        stdscr.clear()

        if h < 10 or w < 40:
            self._safe_addstr(0, 0, "窗口太小")
            stdscr.refresh()
            return

        # 标题栏
        title = " MergeBig - 大文件管理工具 "
        self._safe_addstr(0, max(0, (w - len(title)) // 2), title, curses.A_BOLD)

        # 模式栏
        mode_str = "  ".join(
            f"[{name}]" if i == self.mode_idx else f" {name} "
            for i, (_, name) in enumerate(self.MODES)
        )
        self._safe_addstr(1, 2, mode_str)

        # 分隔线
        self._safe_addstr(2, 0, "─" * (w - 1))

        # 文件列表
        items = self._get_flat_items()
        list_height = h - 5  # 留出行给状态栏和消息

        for row in range(list_height):
            idx = self.scroll_top + row
            y = 3 + row
            if y >= h - 2:
                break

            if idx >= len(items):
                stdscr.move(y, 0)
                stdscr.clrtoeol()
                continue

            item_type, item = items[idx]

            if item_type == "sep":
                line = "─" * min(w - 2, 40)
                self._safe_addstr(y, 2, line, curses.A_DIM)
            else:
                selected = str(item.path) in self.selected
                checkbox = "[x]" if selected else "[ ]"
                size_str = format_size(item.size)
                path_str = str(item.path)

                # 截断路径以适应屏幕
                max_path_len = max(0, w - len(checkbox) - len(size_str) - 6)
                if len(path_str) > max_path_len:
                    path_str = (
                        "..." + path_str[-(max_path_len - 3) :]
                        if max_path_len > 3
                        else path_str[:max_path_len]
                    )

                line = f"{checkbox} {size_str:>12}  {path_str}"

                attrs = 0
                if idx == self.cursor:
                    attrs |= curses.A_REVERSE
                if selected:
                    attrs |= curses.A_BOLD

                self._safe_addstr(y, 2, line, attrs)

        # 消息栏
        msg_y = h - 2
        self._safe_addstr(msg_y, 0, "─" * (w - 1))
        msg = self.message[: w - 1]
        color = curses.color_pair(self.message_color) if curses.has_colors() else 0
        self._safe_addstr(h - 1, 0, msg, color)

        # 快捷键提示（右对齐）
        help_str = "↑↓/kj:移动  Space:选择  a:全选  Enter:执行  Tab:切换  q:退出"
        if len(help_str) < w - len(msg) - 2:
            self._safe_addstr(h - 1, w - len(help_str) - 1, help_str, curses.A_DIM)

        stdscr.refresh()


def run_tui(config: dict):
    tui = TUI(config)
    tui.run()
