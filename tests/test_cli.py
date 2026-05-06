"""测试 cli 模块"""

import pytest
from mergebig.cli import parse_size


class TestParseSize:
    def test_plain_number(self):
        assert parse_size("1024") == 1024

    def test_kilobytes(self):
        assert parse_size("10K") == 10 * 1024
        assert parse_size("10k") == 10 * 1024

    def test_megabytes(self):
        assert parse_size("100M") == 100 * 1024**2
        assert parse_size("100m") == 100 * 1024**2

    def test_gigabytes(self):
        assert parse_size("2G") == 2 * 1024**3
        assert parse_size("2g") == 2 * 1024**3

    def test_terabytes(self):
        assert parse_size("1T") == 1024**4
        assert parse_size("1t") == 1024**4

    def test_whitespace(self):
        assert parse_size("  100M  ") == 100 * 1024**2

    def test_float(self):
        assert parse_size("1.5G") == int(1.5 * 1024**3)
