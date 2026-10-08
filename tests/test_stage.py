"""Tests for scripts/lib/stage.sh (staging the repo for mkarchiso)."""
import os
import subprocess

from conftest import ISO, REPO

STAGE = REPO / "scripts" / "lib" / "stage.sh"


def run(call):
    return subprocess.run(["bash", "-c", f'source "{STAGE}"; {call}'],
                          capture_output=True, text=True)


def test_apply_symlinks_creates_links_and_parents(tmp_path):
    spec = tmp_path / "links.txt"
    spec.write_text("# comment\n\na/b/c.service -> /usr/lib/x.service\nd -> ../rel\n")
    root = tmp_path / "root"
    root.mkdir()
    r = run(f'apply_symlinks "{spec}" "{root}"')
    assert r.returncode == 0, r.stderr
    assert os.readlink(root / "a/b/c.service") == "/usr/lib/x.service"
    assert os.readlink(root / "d") == "../rel"


def test_apply_symlinks_rejects_malformed_line(tmp_path):
    spec = tmp_path / "links.txt"
    spec.write_text("no-arrow-here\n")
    r = run(f'apply_symlinks "{spec}" "{tmp_path}"')
    assert r.returncode != 0
    assert "malformed" in r.stderr


def test_apply_symlinks_on_real_profile(tmp_path):
    r = run(f'apply_symlinks "{ISO / "symlinks.txt"}" "{tmp_path}"')
    assert r.returncode == 0, r.stderr
    assert os.readlink(tmp_path / "etc/systemd/system/display-manager.service").endswith("sddm.service")


def test_swap_kernel_rewrites_profile(tmp_path):
    (tmp_path / "packages.x86_64").write_text("base\nlinux-cachyos\nlinux-cachyos-headers\n")
    entries = tmp_path / "efiboot/loader/entries"
    entries.mkdir(parents=True)
    (entries / "01.conf").write_text("linux /arch/boot/x86_64/vmlinuz-linux-cachyos\n")
    r = run(f'swap_kernel "{tmp_path}" linux-cachyos linux-zen')
    assert r.returncode == 0, r.stderr
    assert (tmp_path / "packages.x86_64").read_text() == "base\nlinux-zen\nlinux-zen-headers\n"
    assert "vmlinuz-linux-zen" in (entries / "01.conf").read_text()


def test_make_branding_images(tmp_path):
    r = run(f'make_branding_images "{tmp_path}"')
    assert r.returncode == 0, r.stderr
    for name, size in (("logo.png", (256, 256)), ("welcome.png", (800, 300))):
        data = (tmp_path / name).read_bytes()
        assert data[:8] == b"\x89PNG\r\n\x1a\n", name
        w, h = int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")
        assert (w, h) == size, name
