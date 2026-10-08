"""Tests for scripts/lib/preflight.sh, run through bash with stubbed system commands."""
import os
import stat
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
PREFLIGHT = REPO / "scripts" / "lib" / "preflight.sh"


@pytest.fixture
def stubs(tmp_path):
    """Directory of fake commands placed first on PATH. Call add(name, script_body)."""
    d = tmp_path / "bin"
    d.mkdir()

    def add(name, body):
        p = d / name
        p.write_text("#!/bin/bash\n" + body + "\n")
        p.chmod(p.stat().st_mode | stat.S_IEXEC)

    add.dir = d
    return add


def run_fn(stubs, call):
    env = dict(os.environ, PATH=f"{stubs.dir}:{os.environ['PATH']}")
    return subprocess.run(
        ["bash", "-c", f'source "{PREFLIGHT}"; {call}'],
        capture_output=True, text=True, env=env,
    )


def test_check_root_fails_for_non_root(stubs):
    stubs("id", 'if [ "$1" = "-u" ]; then echo 1000; fi')
    r = run_fn(stubs, "check_root")
    assert r.returncode != 0
    assert "ERROR: must run as root" in r.stderr


def test_check_root_passes_for_root(stubs):
    stubs("id", 'if [ "$1" = "-u" ]; then echo 0; fi')
    assert run_fn(stubs, "check_root").returncode == 0


def test_check_loop_devices_fails_when_losetup_fails(stubs):
    stubs("losetup", "exit 1")
    r = run_fn(stubs, "check_loop_devices")
    assert r.returncode != 0
    assert "ERROR: no loop devices" in r.stderr


def test_check_disk_space_fails_below_min(stubs):
    stubs("df", 'printf " Avail\\n   10G\\n"')
    r = run_fn(stubs, "check_disk_space /x 20")
    assert r.returncode != 0
    assert "need 20 GB" in r.stderr


def test_check_disk_space_passes_at_min(stubs):
    stubs("df", 'printf " Avail\\n   20G\\n"')
    assert run_fn(stubs, "check_disk_space /x 20").returncode == 0
