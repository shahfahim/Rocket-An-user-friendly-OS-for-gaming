# Rocket OS Phase 1 Test Checklist

Two parts:
- **A. VM dual-boot install**: run by the developer (or Claude) on the build host.
- **B. Live USB on the real laptop**: run by you. Nothing is installed in part B.

## A. VM dual-boot install

Setup (inside the `rocket-build` WSL distro, as root):

```bash
bash tests/install/make-fake-windows-disk.sh /var/tmp/rocket-vm/win.img 100G 1024
bash tests/install/run-install-vm.sh out/RocketOS-*.iso /var/tmp/rocket-vm/win.img
```

| # | Step | Expected | Result |
|---|------|----------|--------|
| A1 | Boot the ISO | "Rocket OS live (UEFI)" entry, then the Plasma desktop logs in automatically as `rocket` | |
| A2 | Open "Install Rocket OS" on the desktop | Calamares opens with Rocket branding | |
| A3 | Partitions page | "Install alongside" is preselected; the slider shrinks the `Windows` NTFS partition | |
| A4 | Finish the install (user `tester`) | Completes with no error dialog | |
| A5 | Reboot and remove the ISO | GRUB menu lists `Rocket OS`, `Rocket snapshots` (after the first snapshot) and a Windows entry | |
| A6 | Boot Rocket OS | SDDM logs into Plasma as `tester` | |
| A7 | `findmnt /` | `subvol=/@` and `compress=zstd:1` | |
| A8 | `sudo snapper list` | Works; config `root` exists | |
| A9 | `sudo pacman -S --noconfirm htop` | Creates a pre/post snapshot pair (`snapper list`) | |
| A10 | `sudo grub-mkconfig -o /boot/grub/grub.cfg` | The `Rocket snapshots` submenu lists the snapshots | |
| A11 | `pacman -Q calamares cachyos-calamares mkinitcpio-archiso` | All three "was not found" | |
| A12 | `id rocket` | "no such user" | |
| A13 | `balooctl6 status` | Indexing is disabled | |
| A14 | `cat /etc/os-release` | `NAME="Rocket OS"` | |
| A15 | `zramctl` | One zram device, about half of RAM, zstd | |
| A16 | `sudo pacman -Sy` | Syncs `cachyos`, `core`, `extra`, `multilib` with no key errors | |

**Negative test:** a 30 GB disk (smaller than the 40 GB requirement):

```bash
bash tests/install/make-fake-windows-disk.sh /var/tmp/rocket-vm/small.img 30G 64
sgdisk --backup=/var/tmp/rocket-vm/small.before /var/tmp/rocket-vm/small.img
```

Boot the ISO with `small.img` and open the installer. Expected: the welcome page says there isn't enough storage and blocks Next. Afterwards, `sgdisk --backup=…after` followed by `cmp` shows the partition table is unchanged.

## B. Real laptop: live USB only (ASUS Vivobook 14 M1405YA)

**Before you start:**
- Flash the ISO with Rufus, using "GPT" and "DD image" mode when Rufus asks.
- In the BIOS (F2 at the ASUS logo), **turn off Secure Boot** for now. Phase 1 doesn't sign the boot loader yet.
- Boot the USB by pressing **ESC** at the ASUS logo and picking the USB drive.

| # | Check | How | Expected | Result |
|---|-------|-----|----------|--------|
| B1 | Boots to desktop | — | Plasma desktop within ~1 minute | |
| B2 | Wi-Fi | Network icon in the tray | Connects to your Wi-Fi | |
| B3 | Bluetooth | Bluetooth icon in the tray | Pairs a device | |
| B4 | Speakers / headphones | Play a YouTube video in Firefox | Sound from both | |
| B5 | Touchpad | Two-finger scroll, tap to click | Works | |
| B6 | Brightness keys | Fn + brightness | Brightness changes | |
| B7 | Suspend / resume | Close and reopen the lid | Resumes to the desktop | |
| B8 | GPU | `vulkaninfo --summary` in Konsole | `AMD Radeon Graphics (RADV RENOIR)` | |
| B9 | CPU driver | `cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_driver` | `amd-pstate-epp` | |
| B10 | Steam | Start Steam from the menu | Updates and reaches the login screen | |

Report any ✗ with a photo of the screen or the command output. Don't run the installer on the laptop until all of part A and part B pass.
