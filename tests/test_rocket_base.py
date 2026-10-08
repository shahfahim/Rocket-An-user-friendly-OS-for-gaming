"""Static checks on the rocket-base package (system defaults for Rocket OS)."""
import re

from conftest import REPO

PKG = REPO / "packages" / "rocket-base"
FILES = PKG


def kv(path):
    """Parse KEY=value / KEY="value" lines into a dict (quotes stripped)."""
    out = {}
    for line in path.read_text().splitlines():
        m = re.match(r'^\s*([A-Z_]+)\s*=\s*"?([^"]*)"?\s*$', line)
        if m:
            out[m.group(1)] = m.group(2)
    return out


def test_os_release_branding():
    rel = kv(FILES / "os-release")
    assert rel["NAME"] == "Rocket OS"
    assert rel["ID"] == "rocketos"
    assert rel["ID_LIKE"] == "arch"
    assert rel["HOME_URL"] == "https://github.com/shahfahim/Rocket-An-user-friendly-OS-for-gaming"


def test_os_release_hook_survives_filesystem_upgrades():
    hook = (FILES / "rocket-os-release.hook").read_text()
    assert "Target = filesystem" in hook
    assert "/etc/os-release" in hook


def test_grub_defaults():
    cfg = kv(FILES / "grub-rocket.cfg")
    assert cfg["GRUB_DISTRIBUTOR"] == "Rocket OS"
    assert cfg["GRUB_TIMEOUT"] == "5"
    assert cfg["GRUB_DISABLE_OS_PROBER"] == "false"
    assert "amd_pstate=active" in cfg["GRUB_CMDLINE_LINUX_DEFAULT"]
    assert "nowatchdog" in cfg["GRUB_CMDLINE_LINUX_DEFAULT"]


def test_grub_defaults_sourced_once():
    install = (PKG / "rocket-base.install").read_text()
    assert ". /etc/default/grub.d/rocket.cfg" in install
    assert "grep -q" in install  # idempotent append


def test_snapper_retention():
    t = kv(FILES / "snapper-rocket")
    assert t["NUMBER_LIMIT"] == "10"
    assert t["TIMELINE_LIMIT_DAILY"] == "7"
    assert t["TIMELINE_LIMIT_HOURLY"] == "0"
    assert t["TIMELINE_CREATE"] == "yes"


def test_baloo_disabled():
    assert re.search(r"^Indexing-Enabled=false$", (FILES / "baloofilerc").read_text(), re.M)


def test_zram_half_ram_zstd():
    text = (FILES / "zram-generator.conf").read_text()
    assert re.search(r"^zram-size = ram / 2$", text, re.M)
    assert re.search(r"^compression-algorithm = zstd$", text, re.M)


def test_pkgbuild_installs_every_file():
    pkgbuild = (PKG / "PKGBUILD").read_text()
    for f in FILES.iterdir():
        if f.name in ("PKGBUILD", "rocket-base.install") or not f.is_file():
            continue
        assert f.name in pkgbuild, f"{f.name} not referenced in PKGBUILD"
    assert re.search(r"^depends=\(.*grub.*\)", pkgbuild, re.M)
