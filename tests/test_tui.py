"""测试 tui 模块"""

import pytest
from pathlib import Path
from mergebig.tui import TUI
from mergebig.scanner import FileInfo


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
