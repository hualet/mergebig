"""测试 tui 模块"""

import pytest
from pathlib import Path
from mergebig.tui import TUI
from mergebig.scanner import FileInfo


class MockStdscr:
    """模拟 curses stdscr，提供 getmaxyx"""

    def __init__(self, h=24, w=80):
        self._size = (h, w)

    def getmaxyx(self):
        return self._size


class TestPrecomputeGroups:
    def test_precompute_large_files(self, tmp_path: Path):
        config = {"path": tmp_path, "min_size": 1, "skip_dirs": set()}
        tui = TUI(config)

        f1 = tmp_path / "a.txt"
        f2 = tmp_path / "b.txt"
        f1.write_bytes(b"x" * 100)
        f2.write_bytes(b"y" * 100)
        tui.files = [FileInfo(f1), FileInfo(f2)]

        tui._precompute_all_groups()
        tui._refresh_groups()

        assert len(tui.groups) == 2
        assert tui.groups[0][0].path == f1
        assert tui.groups[1][0].path == f2

    def test_precompute_dup_hash(self, tmp_path: Path):
        config = {"path": tmp_path, "min_size": 1, "skip_dirs": set()}
        tui = TUI(config)

        f1 = tmp_path / "a.txt"
        f2 = tmp_path / "b.txt"
        f1.write_bytes(b"x" * 100)
        f2.write_bytes(b"x" * 100)
        tui.files = [FileInfo(f1), FileInfo(f2)]

        tui._precompute_all_groups()

        # 切换到 dup_hash 模式
        tui.mode_idx = 1
        tui._refresh_groups()

        assert len(tui.groups) == 1
        assert len(tui.groups[0]) == 2

    def test_precompute_dup_name(self, tmp_path: Path):
        config = {"path": tmp_path, "min_size": 1, "skip_dirs": set()}
        tui = TUI(config)

        d1 = tmp_path / "dir1"
        d2 = tmp_path / "dir2"
        d1.mkdir()
        d2.mkdir()
        f1 = d1 / "same.bin"
        f2 = d2 / "same.bin"
        f1.write_bytes(b"x" * 100)
        f2.write_bytes(b"x" * 100)
        tui.files = [FileInfo(f1), FileInfo(f2)]

        tui._precompute_all_groups()

        # 切换到 dup_name 模式
        tui.mode_idx = 2
        tui._refresh_groups()

        assert len(tui.groups) == 1
        assert len(tui.groups[0]) == 2

    def test_switch_mode_uses_cache(self, tmp_path: Path):
        config = {"path": tmp_path, "min_size": 1, "skip_dirs": set()}
        tui = TUI(config)

        f1 = tmp_path / "a.txt"
        f2 = tmp_path / "b.txt"
        f1.write_bytes(b"x" * 100)
        f2.write_bytes(b"x" * 100)
        tui.files = [FileInfo(f1), FileInfo(f2)]

        tui._precompute_all_groups()

        # 切换到大文件模式
        tui.mode_idx = 0
        tui._refresh_groups()
        large_groups = tui.groups

        # 切换到重复文件模式
        tui.mode_idx = 1
        tui._refresh_groups()
        dup_groups = tui.groups

        # 再切换回大文件模式
        tui.mode_idx = 0
        tui._refresh_groups()

        # 应该使用缓存，结果相同
        assert tui.groups is large_groups
        assert dup_groups is not large_groups


class TestMoveCursor:
    def _make_tui_with_groups(self, tmp_path: Path, groups):
        """构造一个带有指定分组的 TUI 实例"""
        config = {"path": tmp_path, "min_size": 1, "skip_dirs": set()}
        tui = TUI(config)
        tui.stdscr = MockStdscr()
        tui.groups = groups
        tui._group_cache = {
            "large": groups,
            "dup_hash": groups,
            "dup_name": groups,
        }
        tui._refresh_groups()
        return tui

    def test_move_down_skips_separator(self, tmp_path: Path):
        # 构造两组重复文件，中间有分隔线
        f1 = tmp_path / "a.bin"
        f2 = tmp_path / "b.bin"
        f1.write_bytes(b"x" * 100)
        f2.write_bytes(b"y" * 100)
        groups = [[FileInfo(f1)], [FileInfo(f2)]]

        tui = self._make_tui_with_groups(tmp_path, groups)
        assert tui.cursor == 0  # 第一个文件项

        tui._move_cursor(1)
        # 应该跳过中间的分隔线，落到第二个文件项
        items = tui._get_flat_items()
        assert items[tui.cursor][0] == "file"
        assert items[tui.cursor][1].path == f2

    def test_move_up_skips_separator(self, tmp_path: Path):
        f1 = tmp_path / "a.bin"
        f2 = tmp_path / "b.bin"
        f1.write_bytes(b"x" * 100)
        f2.write_bytes(b"y" * 100)
        groups = [[FileInfo(f1)], [FileInfo(f2)]]

        tui = self._make_tui_with_groups(tmp_path, groups)
        # 手动把光标放到最后一项
        tui.cursor = 2  # file, sep, file

        tui._move_cursor(-1)
        items = tui._get_flat_items()
        assert items[tui.cursor][0] == "file"
        assert items[tui.cursor][1].path == f1

    def test_move_down_at_last_item_stays(self, tmp_path: Path):
        f1 = tmp_path / "a.bin"
        f1.write_bytes(b"x" * 100)
        groups = [[FileInfo(f1)]]

        tui = self._make_tui_with_groups(tmp_path, groups)
        tui._move_cursor(1)
        items = tui._get_flat_items()
        assert items[tui.cursor][0] == "file"
        assert items[tui.cursor][1].path == f1

    def test_move_up_at_first_item_stays(self, tmp_path: Path):
        f1 = tmp_path / "a.bin"
        f1.write_bytes(b"x" * 100)
        groups = [[FileInfo(f1)]]

        tui = self._make_tui_with_groups(tmp_path, groups)
        tui._move_cursor(-1)
        items = tui._get_flat_items()
        assert items[tui.cursor][0] == "file"
        assert items[tui.cursor][1].path == f1
