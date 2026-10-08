"""Static checks on the Calamares installer configuration in installer/calamares/."""
import re

import pytest
import yaml

from conftest import REPO

CAL = REPO / "installer" / "calamares"
MODS = CAL / "modules"


def load(path):
    return yaml.safe_load(path.read_text())


@pytest.fixture
def settings():
    return load(CAL / "settings.conf")


def exec_steps(settings):
    steps = []
    for phase in settings["sequence"]:
        steps += phase.get("exec", [])
    return steps


def show_steps(settings):
    steps = []
    for phase in settings["sequence"]:
        steps += phase.get("show", [])
    return steps


# --- Task 5: branding and module sequence ---

def test_exec_sequence_order(settings):
    s = exec_steps(settings)
    i = s.index
    assert i("partition") < i("mount") < i("unpackfs")
    # live-session cleanup runs right after unpacking, before Calamares writes users/DM config
    assert i("unpackfs") < i("shellprocess@rocket-post") < i("users") < i("displaymanager")
    assert i("shellprocess@rocket-post") < i("initcpio") < i("bootloader") < i("shellprocess@rocket-grub")
    assert s[-1] == "umount"
    assert "removeuser" not in s  # live user is created at boot, never in the image


def test_show_sequence(settings):
    assert show_steps(settings) == ["welcome", "locale", "keyboard", "partition", "users", "summary", "finished"]


def test_branding_name(settings):
    assert settings["branding"] == "rocket"
    desc = load(CAL / "branding" / "rocket" / "branding.desc")
    assert desc["componentName"] == "rocket"
    assert desc["strings"]["productName"] == "Rocket OS"


def test_branding_images_declared_exist_or_generated(settings):
    desc = load(CAL / "branding" / "rocket" / "branding.desc")
    # Images are generated at build time (no binary assets in git); names must be fixed.
    assert desc["images"]["productLogo"] == "logo.png"
    assert desc["images"]["productIcon"] == "logo.png"
    assert desc["images"]["productWelcome"] == "welcome.png"
    assert (CAL / "branding" / "rocket" / desc["slideshow"]).exists()


def test_instances_declared(settings):
    inst = {i["id"]: i for i in settings["instances"]}
    for name in ("rocket-post", "rocket-grub"):
        assert inst[name]["module"] == "shellprocess"
        assert (MODS / inst[name]["config"]).exists(), inst[name]["config"]


# --- Task 6: partitioning, mounts and system modules ---
AIROOT = REPO / "iso" / "airootfs"
POST = AIROOT / "usr/local/bin/rocket-post-install"


def test_every_configurable_module_has_rocket_config(settings):
    """Don't silently fall back to the distro package's defaults (cachyos-calamares)."""
    needs_conf = {"welcome", "locale", "keyboard", "partition", "users", "finished", "mount",
                  "unpackfs", "machineid", "fstab", "displaymanager", "services-systemd",
                  "initcpio", "bootloader"}
    used = {s for s in show_steps(settings) + exec_steps(settings) if "@" not in s}
    missing = [m for m in sorted(needs_conf & used) if not (MODS / f"{m}.conf").exists()]
    assert not missing, missing


def test_welcome_requirements():
    w = load(MODS / "welcome.conf")["requirements"]
    assert w["requiredStorage"] == 40
    assert w["requiredRam"] == 4.0
    assert set(w["required"]) == {"storage", "ram"}


def test_alongside_default():
    assert load(MODS / "partition.conf")["initialPartitioningChoice"] == "alongside"


def test_btrfs_only():
    p = load(MODS / "partition.conf")
    assert p["defaultFileSystemType"] == "btrfs"
    assert p["availableFileSystemTypes"] == ["btrfs"]


def test_esp_reused_at_boot_efi():
    efi = load(MODS / "partition.conf")["efi"]
    assert efi["mountPoint"] == "/boot/efi"
    assert "forceFormat" not in str(load(MODS / "partition.conf"))


def test_no_swap_partition():
    p = load(MODS / "partition.conf")
    assert p["userSwapChoices"] == ["none"]
    assert p["initialSwapChoice"] == "none"


def test_luks_offered():
    assert load(MODS / "partition.conf")["enableLuksAutomatedPartitioning"] is True


def test_subvolumes_exact():
    subs = {s["mountPoint"]: s["subvolume"].lstrip("/") for s in load(MODS / "mount.conf")["btrfsSubvolumes"]}
    assert subs == {"/": "@", "/home": "@home", "/.snapshots": "@snapshots",
                    "/var/log": "@var_log", "/games": "@games"}


def test_btrfs_mount_options():
    opts = {o["filesystem"]: o["options"] for o in load(MODS / "mount.conf")["mountOptions"]}
    assert opts["btrfs"] == ["defaults", "noatime", "compress=zstd:1"]
    assert "umask=0077" in opts["efi"]


def test_kernel_copied_into_target():
    unpack = load(MODS / "unpackfs.conf")["unpack"]
    assert unpack[0]["source"] == "/run/archiso/bootmnt/arch/x86_64/airootfs.sfs"
    assert unpack[0]["sourcefs"] == "squashfs"
    kern = [u for u in unpack if u["sourcefs"] == "file"]
    assert kern and kern[0]["source"].endswith("/arch/boot/x86_64/vmlinuz-linux-cachyos")
    assert kern[0]["destination"] == "/boot/vmlinuz-linux-cachyos"


def test_initcpio_kernel():
    assert load(MODS / "initcpio.conf")["kernel"] == "linux-cachyos"


def test_users():
    u = load(MODS / "users.conf")
    groups = [g if isinstance(g, str) else g["name"] for g in u["defaultGroups"]]
    assert {"wheel", "video", "audio", "input"} <= set(groups)
    assert u["sudoersGroup"] == "wheel"
    assert u["doAutologin"] is True
    assert u["setRootPassword"] is False
    assert u["passwordRequirements"]["minLength"] == 4


def test_displaymanager_sddm_plasma():
    d = load(MODS / "displaymanager.conf")
    assert d["displaymanagers"] == ["sddm"]
    assert d["defaultDesktopEnvironment"]["desktopFile"] == "plasma"


def test_services_enabled():
    units = {u["name"] for u in load(MODS / "services-systemd.conf")["units"] if u["action"] == "enable"}
    assert units == {"NetworkManager.service", "bluetooth.service", "sddm.service", "fstrim.timer",
                     "snapper-timeline.timer", "snapper-cleanup.timer", "grub-btrfsd.service"}


def test_rocket_post_runs_cleanup_script():
    conf = load(MODS / "shellprocess-rocket-post.conf")
    assert conf["dontChroot"] is False
    assert any("/usr/local/bin/rocket-post-install" in str(c) for c in conf["script"])


@pytest.mark.parametrize("artifact", [
    "/etc/sudoers.d/rocket-live", "/etc/sddm.conf.d/autologin.conf", "rocket-live-user",
    "/usr/local/share/rocket-live", "/etc/mkinitcpio.conf.d/archiso.conf", "pacman-init.service",
    "etc-pacman.d-gnupg.mount", "volatile-storage.conf", "/etc/calamares", "mkinitcpio-archiso",
    "/usr/share/rocket/calamares",
])
def test_live_artifacts_removed(artifact):
    assert artifact in POST.read_text()


def test_post_removes_calamares_package_by_owner():
    assert re.search(r"pacman -Qqo /usr/bin/calamares", POST.read_text())


def test_post_initialises_keyring():
    text = POST.read_text()
    assert "pacman-key --init" in text
    assert "pacman-key --populate" in text


def test_snapper_uses_rocket_template():
    text = POST.read_text()
    assert "create-config -t rocket /" in text
    assert "subvol=@snapshots" in text


def test_post_script_permissions():
    assert '["/usr/local/bin/rocket-post-install"]="0:0:755"' in (REPO / "iso/profiledef.sh").read_text()


def test_installed_pacman_conf_has_cachyos_and_multilib_not_local_repo():
    text = (AIROOT / "etc/pacman.conf").read_text()
    secs = re.findall(r"^\[([^\]]+)\]", text, re.M)
    assert [s for s in secs if s != "options"] == ["cachyos", "core", "extra", "multilib"]


def test_cachyos_keyring_and_mirrorlist_installed():
    from conftest import read_packages
    pkgs = read_packages()
    assert "cachyos-keyring" in pkgs and "cachyos-mirrorlist" in pkgs


# --- Task 7: bootloader, Windows entry, snapshots menu ---
GRUB_SETUP = AIROOT / "usr/local/bin/rocket-grub-setup"


def test_bootloader_grub_no_fallback_overwrite():
    b = load(MODS / "bootloader.conf")
    assert b["efiBootLoader"] == "grub"
    assert b["efiBootloaderId"] == "RocketOS"
    assert b["installEFIFallback"] is False  # never overwrite \EFI\BOOT\BOOTX64.EFI


def test_rocket_grub_runs_setup_script():
    conf = load(MODS / "shellprocess-rocket-grub.conf")
    assert conf["dontChroot"] is False
    assert any("/usr/local/bin/rocket-grub-setup" in str(c) for c in conf["script"])


def test_windows_fallback_entry():
    text = GRUB_SETUP.read_text()
    assert "chainloader /EFI/Microsoft/Boot/bootmgfw.efi" in text
    assert "[ -f /boot/efi/EFI/Microsoft/Boot/bootmgfw.efi ]" in text
    assert "/etc/grub.d/40_custom" in text
    assert "Windows Boot Manager (fallback)" in text


def test_windows_fallback_only_when_os_prober_missed_it():
    assert re.search(r"grep -q .*Windows Boot Manager.* /boot/grub/grub.cfg", GRUB_SETUP.read_text())


def test_snapshot_submenu_name():
    assert 'GRUB_BTRFS_SUBMENUNAME="Rocket snapshots"' in GRUB_SETUP.read_text()


def test_grub_setup_permissions():
    assert '["/usr/local/bin/rocket-grub-setup"]="0:0:755"' in (REPO / "iso/profiledef.sh").read_text()


def test_post_install_keeps_grub_setup_for_later():
    # rocket-post-install runs first and must not delete the grub script.
    assert "rocket-grub-setup" not in POST.read_text()
