"""Tests for tests/install/make-fake-windows-disk.sh (needs root for losetup/mount)."""
import os
import re
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).with_name("make-fake-windows-disk.sh")

pytestmark = pytest.mark.skipif(os.geteuid() != 0, reason="needs root (losetup, mount)")


@pytest.fixture(scope="module")
def disk(tmp_path_factory):
    img = tmp_path_factory.mktemp("disk") / "win.img"
    r = subprocess.run(["bash", str(SCRIPT), str(img), "1G", "64"], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    return img


def test_partition_layout_matches_windows(disk):
    out = subprocess.run(["sgdisk", "-p", str(disk)], capture_output=True, text=True).stdout
    rows = re.findall(r"^\s+(\d+)\s+\d+\s+\d+\s+\S+ \S+\s+([0-9A-F]{4})", out, re.M)
    assert rows == [("1", "EF00"), ("2", "0C01"), ("3", "0700")], out


def test_esp_has_windows_boot_manager(disk):
    start = int(re.search(r"^\s+1\s+(\d+)", subprocess.run(
        ["sgdisk", "-p", str(disk)], capture_output=True, text=True).stdout, re.M).group(1))
    r = subprocess.run(["mdir", "-i", f"{disk}@@{start * 512}", "::/EFI/Microsoft/Boot"],
                       capture_output=True, text=True)
    assert "bootmgfw" in r.stdout.lower(), r.stdout + r.stderr


def test_ntfs_partition_has_filler(disk):
    r = subprocess.run(["bash", "-c", f'''
        set -e; dev=$(losetup -fP --show "{disk}"); trap "losetup -d $dev" EXIT
        ntfsls "${{dev}}p3"'''], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert "filler.bin" in r.stdout
