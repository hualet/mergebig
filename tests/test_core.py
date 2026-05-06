"""测试 core 模块"""

import os
from pathlib import Path
from mergebig.scanner import FileInfo
from mergebig.core import delete_files, hardlink_files, calculate_wasted_space


class TestDeleteFiles:
    def test_deletes_existing_files(self, tmp_path: Path):
        f1 = tmp_path / "a.txt"
        f2 = tmp_path / "b.txt"
        f1.write_text("hello")
        f2.write_text("world")
        files = [FileInfo(f1), FileInfo(f2)]
        success, failed = delete_files(files)
        assert success == 2
        assert len(failed) == 0
        assert not f1.exists()
        assert not f2.exists()

    def test_reports_missing_files(self, tmp_path: Path):
        f1 = tmp_path / "a.txt"
        f1.write_text("hello")
        files = [FileInfo(f1)]
        # 先删除文件，再传给 delete_files
        f1.unlink()
        success, failed = delete_files(files)
        assert success == 0
        assert len(failed) == 1


class TestHardlinkFiles:
    def test_hardlinks_duplicates(self, tmp_path: Path):
        f1 = tmp_path / "a.bin"
        f2 = tmp_path / "b.bin"
        f1.write_bytes(b"x" * 100)
        f2.write_bytes(b"x" * 100)
        group = [FileInfo(f1), FileInfo(f2)]
        success, failed = hardlink_files([group])
        assert success == 1
        assert len(failed) == 0
        assert f2.exists()
        assert f1.stat().st_ino == f2.stat().st_ino

    def test_ignores_single_file_groups(self, tmp_path: Path):
        f1 = tmp_path / "a.bin"
        f1.write_bytes(b"x" * 100)
        success, failed = hardlink_files([[FileInfo(f1)]])
        assert success == 0
        assert len(failed) == 0

    def test_keeps_first_as_master(self, tmp_path: Path):
        f1 = tmp_path / "a.bin"
        f2 = tmp_path / "b.bin"
        f3 = tmp_path / "c.bin"
        f1.write_bytes(b"x" * 100)
        f2.write_bytes(b"x" * 100)
        f3.write_bytes(b"x" * 100)
        group = [FileInfo(f2), FileInfo(f3), FileInfo(f1)]
        # sorted by path: a.bin, b.bin, c.bin -> a.bin is master
        success, failed = hardlink_files([group])
        assert success == 1
        ino = f1.stat().st_ino
        assert f2.stat().st_ino == ino
        assert f3.stat().st_ino == ino


class TestCalculateWastedSpace:
    def test_empty(self):
        assert calculate_wasted_space([]) == 0

    def test_single_group(self):
        class FakeFile:
            def __init__(self, size):
                self.size = size

        group = [FakeFile(100), FakeFile(100), FakeFile(100)]
        assert calculate_wasted_space([group]) == 200

    def test_multiple_groups(self):
        class FakeFile:
            def __init__(self, size):
                self.size = size

        g1 = [FakeFile(100), FakeFile(100)]
        g2 = [FakeFile(50), FakeFile(50), FakeFile(50)]
        assert calculate_wasted_space([g1, g2]) == 100 + 100

    def test_ignores_single_files(self):
        class FakeFile:
            def __init__(self, size):
                self.size = size

        g1 = [FakeFile(100)]
        assert calculate_wasted_space([g1]) == 0
