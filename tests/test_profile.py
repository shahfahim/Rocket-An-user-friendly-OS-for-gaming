"""Static checks on the archiso profile in iso/."""
import re
import subprocess

import pytest

from conftest import ISO, REPO, bash_array, read_packages

BASE = """base linux-cachyos linux-cachyos-headers linux-firmware amd-ucode btrfs-progs grub
efibootmgr os-prober snapper grub-btrfs snap-pac zram-generator sbctl ntfs-3g dosfstools""".split()
GRAPHICS = "mesa lib32-mesa vulkan-radeon lib32-vulkan-radeon libva-mesa-driver".split()
DESKTOP = """plasma-desktop plasma-nm plasma-pa powerdevil kscreen bluedevil breeze-gtk dolphin
konsole ark spectacle sddm sddm-kcm firefox networkmanager bluez bluez-utils pipewire
pipewire-pulse wireplumber""".split()
GAMING = ["steam"]
INSTALLER = "calamares rocket-base arch-install-scripts mkinitcpio-archiso".split()
BANNED = "baloo-widgets kdeconnect cups avahi modemmanager archinstall".split()

# Packages built locally into the [rocket] repo, not resolvable from remote repos.
LOCAL = {"rocket-base"}


def test_bootmodes_uefi_only():
    modes = bash_array((ISO / "profiledef.sh").read_text(), "bootmodes")
    assert modes, "no bootmodes"
    assert all(m.startswith("uefi.") for m in modes), modes


def test_iso_name_and_label():
    text = (ISO / "profiledef.sh").read_text()
    assert 'iso_name="RocketOS"' in text
    assert re.search(r'iso_label="ROCKET_\$\(date', text)


@pytest.mark.parametrize("group", [BASE, GRAPHICS, DESKTOP, GAMING, INSTALLER])
def test_required_packages_present(packages, group):
    missing = [p for p in group if p not in packages]
    assert not missing, f"missing from packages.x86_64: {missing}"


def test_no_duplicate_packages(packages):
    dups = sorted({p for p in packages if packages.count(p) > 1})
    assert not dups, dups


def test_no_banned_packages(packages):
    assert not [p for p in packages if p in BANNED]


def sections(conf_text):
    return re.findall(r"^\[([^\]]+)\]", conf_text, re.M)


def test_pacman_conf_repo_order():
    secs = [s for s in sections((ISO / "pacman.conf").read_text()) if s != "options"]
    assert secs == ["cachyos", "core", "extra", "multilib", "rocket"], secs


def test_rocket_repo_points_at_work_dir():
    text = (ISO / "pacman.conf").read_text()
    m = re.search(r"^\[rocket\]\n(?:.*\n)*?Server\s*=\s*(\S+)", text, re.M)
    assert m and m.group(1) == "file:///var/tmp/rocket-work/repo"


def test_live_boot_entries_use_cachyos_kernel():
    entries = [f for f in (ISO / "efiboot" / "loader" / "entries").glob("*.conf")
               if re.search(r"^linux\s", f.read_text(), re.M)]
    assert entries, "no live kernel boot entries"
    for f in entries:
        text = f.read_text()
        assert "vmlinuz-linux-cachyos" in text, f.name
        assert "initramfs-linux-cachyos.img" in text, f.name


@pytest.mark.network
def test_packages_resolve(tmp_path):
    """Every package must exist in the configured repos (except locally built ones)."""
    conf = (ISO / "pacman.conf").read_text()
    # Drop the local repo: it only exists during a build.
    conf = re.sub(r"^\[rocket\]\n(?:[^\[].*\n?)*", "", conf, flags=re.M)
    (tmp_path / "pacman.conf").write_text(conf)
    db = tmp_path / "db"
    (db / "local").mkdir(parents=True)
    sync = subprocess.run(
        ["fakeroot", "pacman", "--config", str(tmp_path / "pacman.conf"), "--dbpath", str(db), "-Sy"],
        capture_output=True, text=True,
    )
    assert sync.returncode == 0, sync.stderr
    pkgs = [p for p in read_packages() if p not in LOCAL]
    r = subprocess.run(
        ["pacman", "--config", str(tmp_path / "pacman.conf"), "--dbpath", str(db),
         "-Sp", "--print-format", "%n", *pkgs],
        capture_output=True, text=True,
    )
    unresolved = re.findall(r"target not found: (\S+)", r.stderr)
    assert r.returncode == 0, f"unresolved packages: {unresolved or r.stderr[-500:]}"


# --- Task 3: live session overlay ---
AIROOT = ISO / "airootfs"


def symlinks():
    links = {}
    for line in (ISO / "symlinks.txt").read_text().splitlines():
        if line.strip() and not line.startswith("#"):
            link, target = (s.strip() for s in line.split("->"))
            links[link] = target
    return links


def test_live_autologin_plasma():
    text = (AIROOT / "etc/sddm.conf.d/autologin.conf").read_text()
    assert re.search(r"^User=rocket$", text, re.M)
    assert re.search(r"^Session=plasma$", text, re.M)


def test_display_manager_is_sddm():
    assert symlinks()["etc/systemd/system/display-manager.service"].endswith("/sddm.service")


def test_networkmanager_enabled():
    assert "etc/systemd/system/multi-user.target.wants/NetworkManager.service" in symlinks()


def test_live_user_created_before_login():
    unit = (AIROOT / "etc/systemd/system/rocket-live-user.service").read_text()
    assert "Before=display-manager.service" in unit
    assert "etc/systemd/system/multi-user.target.wants/rocket-live-user.service" in symlinks()
    script = (AIROOT / "usr/local/bin/rocket-live-user").read_text()
    assert re.search(r"useradd -m .*-G wheel.* rocket", script)


def test_sudoers_permissions():
    perms = (ISO / "profiledef.sh").read_text()
    assert '["/etc/sudoers.d/rocket-live"]="0:0:440"' in perms
    assert '["/usr/local/bin/rocket-live-user"]="0:0:755"' in perms
    assert "rocket ALL=(ALL) NOPASSWD: ALL" in (AIROOT / "etc/sudoers.d/rocket-live").read_text()


def test_installer_launcher_present():
    text = (AIROOT / "usr/local/share/rocket-live/install-rocket.desktop").read_text()
    assert "Name=Install Rocket OS" in text
    assert re.search(r"^Exec=.*calamares", text, re.M)
