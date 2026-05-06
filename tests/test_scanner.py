"""测试 scanner 模块"""

import pytest
from pathlib import Path
from mergebig.scanner import (
    format_size,
    quick_hash,
    full_hash,
    FileInfo,
    scan_large_files,
    find_duplicates_by_hash,
    find_duplicates_by_name,
)


class TestFormatSize:
    def test_bytes(self):
        assert format_size(512) == "512.00 B"

    def test_kilobytes(self):
        assert format_size(1536) == "1.50 KB"

    def test_megabytes(self):
        assert format_size(2 * 1024**2) == "2.00 MB"

    def test_gigabytes(self):
        assert format_size(3 * 1024**3) == "3.00 GB"

    def test_zero(self):
        assert format_size(0) == "0.00 B"


class TestHash:
    def test_quick_hash_same_content_same_size(self, tmp_path: Path):
        f1 = tmp_path / "a.txt"
        f2 = tmp_path / "b.txt"
        f1.write_bytes(b"hello world")
        f2.write_bytes(b"hello world")
        assert quick_hash(f1) == quick_hash(f2)

    def test_quick_hash_different_content(self, tmp_path: Path):
        f1 = tmp_path / "a.txt"
        f2 = tmp_path / "b.txt"
        f1.write_bytes(b"hello")
        f2.write_bytes(b"world")
        assert quick_hash(f1) != quick_hash(f2)

    def test_quick_hash_different_size(self, tmp_path: Path):
        f1 = tmp_path / "a.txt"
        f2 = tmp_path / "b.txt"
        f1.write_bytes(b"hello")
        f2.write_bytes(b"hello!")
        assert quick_hash(f1) != quick_hash(f2)

    def test_full_hash_differs_from_quick(self, tmp_path: Path):
        # quick_hash 包含文件大小作为额外输入，所以结果不同
        f = tmp_path / "a.txt"
        f.write_bytes(b"small file content")
        assert quick_hash(f) != full_hash(f)
        # 但完整 hash 应该与直接 sha256 一致
        import hashlib
        hasher = hashlib.sha256()
        hasher.update(b"small file content")
        assert full_hash(f) == hasher.hexdigest()

    def test_hash_nonexistent_file(self, tmp_path: Path):
        assert quick_hash(tmp_path / "nope.txt") is None
        assert full_hash(tmp_path / "nope.txt") is None


class TestFileInfo:
    def test_basic(self, tmp_path: Path):
        f = tmp_path / "test.txt"
        f.write_bytes(b"12345")
        info = FileInfo(f)
        assert info.path == f
        assert info.name == "test.txt"
        assert info.size == 5
        assert info.quick_hash is None
        assert info.full_hash is None


class TestScanLargeFiles:
    def test_finds_large_files(self, tmp_path: Path):
        large = tmp_path / "large.bin"
        small = tmp_path / "small.txt"
        large.write_bytes(b"x" * 100)
        small.write_bytes(b"x" * 10)
        results = scan_large_files(tmp_path, 50, set())
        assert len(results) == 1
        assert results[0].path == large

    def test_skips_hidden_dirs(self, tmp_path: Path):
        hidden = tmp_path / ".hidden" / "large.bin"
        hidden.parent.mkdir()
        hidden.write_bytes(b"x" * 100)
        results = scan_large_files(tmp_path, 50, set())
        assert len(results) == 0

    def test_skips_skip_dirs(self, tmp_path: Path):
        skip = tmp_path / "node_modules" / "large.bin"
        skip.parent.mkdir()
        skip.write_bytes(b"x" * 100)
        results = scan_large_files(tmp_path, 50, {"node_modules"})
        assert len(results) == 0

    def test_progress_callback(self, tmp_path: Path):
        (tmp_path / "a.txt").write_bytes(b"x" * 100)
        calls = []
        scan_large_files(tmp_path, 50, set(), progress_callback=lambda s: calls.append(s))
        assert len(calls) >= 1
        assert calls[-1]["files_checked"] == 1
        assert calls[-1]["large_files_found"] == 1


class TestFindDuplicatesByHash:
    def test_finds_duplicates(self, tmp_path: Path):
        f1 = tmp_path / "a.bin"
        f2 = tmp_path / "b.bin"
        f3 = tmp_path / "c.bin"
        f1.write_bytes(b"x" * 100)
        f2.write_bytes(b"x" * 100)
        f3.write_bytes(b"y" * 100)
        files = [FileInfo(f) for f in [f1, f2, f3]]
        dups = find_duplicates_by_hash(files)
        assert len(dups) == 1
        assert len(dups[0]) == 2
        paths = {str(f.path) for f in dups[0]}
        assert paths == {str(f1), str(f2)}

    def test_no_duplicates(self, tmp_path: Path):
        f1 = tmp_path / "a.bin"
        f2 = tmp_path / "b.bin"
        f1.write_bytes(b"x" * 100)
        f2.write_bytes(b"y" * 100)
        files = [FileInfo(f) for f in [f1, f2]]
        dups = find_duplicates_by_hash(files)
        assert len(dups) == 0


class TestFindDuplicatesByName:
    def test_finds_same_name_same_content(self, tmp_path: Path):
        d1 = tmp_path / "dir1"
        d2 = tmp_path / "dir2"
        d1.mkdir()
        d2.mkdir()
        f1 = d1 / "same.bin"
        f2 = d2 / "same.bin"
        f1.write_bytes(b"x" * 100)
        f2.write_bytes(b"x" * 100)
        files = [FileInfo(f) for f in [f1, f2]]
        dups = find_duplicates_by_name(files)
        assert len(dups) == 1
        assert len(dups[0]) == 2

    def test_same_name_different_content(self, tmp_path: Path):
        d1 = tmp_path / "dir1"
        d2 = tmp_path / "dir2"
        d1.mkdir()
        d2.mkdir()
        f1 = d1 / "same.bin"
        f2 = d2 / "same.bin"
        f1.write_bytes(b"x" * 100)
        f2.write_bytes(b"y" * 100)
        files = [FileInfo(f) for f in [f1, f2]]
        dups = find_duplicates_by_name(files)
        assert len(dups) == 0
