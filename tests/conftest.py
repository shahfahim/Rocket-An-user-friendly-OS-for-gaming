import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
ISO = REPO / "iso"


def pytest_configure(config):
    config.addinivalue_line("markers", "network: needs network access to package repos")


def read_packages(path=ISO / "packages.x86_64"):
    pkgs = []
    for line in path.read_text().splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            pkgs.append(line)
    return pkgs


def bash_array(text, name):
    """Return the items of a bash array assignment `name=( ... )`."""
    m = re.search(rf"^{name}=\((.*?)\)", text, re.S | re.M)
    assert m, f"{name} not found"
    tokens = re.findall(r"'([^']*)'|\"([^\"]*)\"|(\S+)", m.group(1))
    return [a or b or c for a, b, c in tokens]


@pytest.fixture
def packages():
    return read_packages()
