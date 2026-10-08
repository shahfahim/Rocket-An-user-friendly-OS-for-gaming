# Rocket OS Phase 1: Bootable, Installable Base. Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce `out/RocketOS-<date>-x86_64.iso` that boots a live KDE Plasma session with Steam on UEFI, and installs alongside Windows with Calamares onto btrfs. The installed system boots via GRUB, which lists Rocket OS, Rocket snapshots and Windows.

**Architecture:**
- A `build.ps1` on Windows provisions an Arch Linux WSL2 distro (`rocket-build`) and runs `build.sh` inside it.
- `build.sh` builds local `rocket-*` packages into a repo, then runs `mkarchiso` on the `iso/` profile, which is derived from archiso's `releng`.
- Calamares, with config in `installer/`, unpacks the live squashfs onto btrfs subvolumes. Post-install shell processes then configure GRUB, os-prober, snapper and grub-btrfs, and strip live-only packages.

**Tech Stack:**
- archiso, pacman/makepkg
- CachyOS repos (kernel `linux-cachyos`, `calamares`)
- KDE Plasma 6, SDDM, GRUB, btrfs, snapper, grub-btrfs, snap-pac
- QEMU + OVMF for boot tests
- pytest for static profile tests
- PowerShell 5.1 for the Windows entry point

**Spec:** `docs/superpowers/specs/2026-10-08-rocket-os-design.md` (Phase 1 = spec §13 item 1; draws on §4, §5.1, §8 Secure Boot note, §9, §10, §11, §12)

## Global Constraints

- Target: UEFI-only x86_64 (ASUS M1405YA, Ryzen 7 7730U, Vega 8). No BIOS/legacy boot modes.
- Kernel: `linux-cachyos`. If the CachyOS repos are unreachable at build time, fall back to `linux-zen` (spec §14).
- Filesystem: btrfs, mount options `compress=zstd:1,noatime`, subvolumes `@`, `@home`, `@snapshots`, `@var_log`, `@games`.
- Partitioning: "Install alongside" is the default, with a suggested Rocket size of 300 GB. Reuse the existing EFI partition (mount at `/boot/efi`) and never format it.
- Bootloader: GRUB with `GRUB_DISABLE_OS_PROBER=false`, `GRUB_TIMEOUT=5`, default entry Rocket OS; grub-btrfs provides the "Rocket snapshots" submenu.
- Snapshot retention: `NUMBER_LIMIT=10`, `TIMELINE_LIMIT_DAILY=7`, `TIMELINE_LIMIT_HOURLY=0`.
- ISO name `RocketOS-<YYYY.MM.DD>-x86_64.iso` plus a `.sha256` file; volume label `ROCKET_<YYYYMM>`.
- Live user: `rocket`, autologin to Plasma. On the installed system, the user is created by Calamares, and the live user and `calamares` package are removed.
- No telemetry packages; no Baloo indexing (`baloofile` disabled via `/etc/xdg/baloofilerc`).
- Every script uses `set -euo pipefail` (bash) or `$ErrorActionPreference='Stop'` (PowerShell).
- Commit after each task and push to `origin main`.

## Review Focus

- **BitLocker-encrypted or dirty NTFS:** the "alongside" resize must fail before any write, with a readable message. Calamares itself shows this check, and Task 6's config pins `requiredStorage` and `alongside` behavior; Task 8's manual checklist verifies it.
- **Existing EFI partition is small (100 MB on many OEM Windows installs):** the GRUB install must fit. Task 7 pins `grub-install --removable=no` with no extra fonts/themes in the ESP (< 5 MB used).
- **WSL2 build host without loop devices/privileges:** `build.sh` must detect this and stop with an actionable message instead of producing a half-built ISO. Task 1 adds a test.
- **Package that no longer exists in the repos:** the build must fail before `mkarchiso` with the missing package name. Task 2 adds a `pacman -Sp` resolution test.
- **Windows missing from GRUB after install (os-prober can't see NTFS from chroot):** Task 7 adds a fallback custom entry that chainloads `bootmgfw.efi`. Its test asserts the entry exists in `40_custom`.

---

## File Structure

```
build.ps1                                Windows entry: create WSL distro, invoke build.sh
build.sh                                 Inside WSL: preflight, build packages, mkarchiso, checksum
scripts/setup-build-host.sh              One-time host setup inside WSL (archiso, base-devel, cachyos keys)
scripts/lib/preflight.sh                 check_root, check_loop_devices, check_disk_space (sourced)
iso/profiledef.sh                        archiso profile definition
iso/pacman.conf                          core, extra, multilib, cachyos repos + [rocket] local repo
iso/packages.x86_64                      live/installed package list
iso/efiboot/loader/entries/*.conf        systemd-boot live entries (UEFI live boot)
iso/grub/grub.cfg                        archiso grub (for uefi.grub boot mode)
iso/airootfs/etc/...                     live overlay (sddm autologin, hostname, locale, services)
iso/symlinks.txt                         symlinks recreated inside WSL before mkarchiso (Windows git can't hold them)
packages/rocket-base/PKGBUILD            Rocket base config: os-release, grub defaults, snapper template, baloo off
packages/rocket-base/files/...
installer/calamares/settings.conf
installer/calamares/modules/*.conf
installer/calamares/branding/rocket/branding.desc (+ images)
tests/test_profile.py                    static pytest checks on iso/, installer/, packages/
tests/test_preflight.py                  runs preflight functions via bash with stubbed commands
tests/test_installer.py                  static pytest checks on installer/calamares YAML
tests/boot/qemu-boot.sh                  automated UEFI boot test of the ISO
tests/install/make-fake-windows-disk.sh  creates a qcow2 with ESP + NTFS for manual install test
docs/testing/phase1-checklist.md         manual VM install + real-hardware live checklist
```

---

### Task 1: Build host and preflight

**Files:**
- Create: `build.ps1`
- Create: `scripts/setup-build-host.sh`
- Create: `scripts/lib/preflight.sh`
- Create: `build.sh` (preflight + skeleton; calls `mkarchiso` in Task 4)
- Test: `tests/test_preflight.py`

**Interfaces:**
- Produces:
  - `build.ps1 [-Clean]`: creates the WSL distro `rocket-build` if missing (`wsl --install archlinux --name rocket-build --no-launch`), runs `scripts/setup-build-host.sh` once (marker file `/var/lib/rocket-build/ready`), then runs `build.sh` as root. The repo path is translated with `wsl wslpath`.
  - `scripts/lib/preflight.sh` functions, each returning non-zero and printing `ERROR: <reason>. Fix: <hint>` on failure:
    - `check_root`
    - `check_loop_devices` (`losetup -f` succeeds)
    - `check_disk_space <dir> <min_gb>` (min 20 GB for the work dir)
  - `ROCKET_WORK=/var/tmp/rocket-work` (on the WSL ext4 disk, never on `/mnt/e`, because NTFS breaks mkarchiso permissions).

- [ ] **Step 1: Write failing tests.** `tests/test_preflight.py` runs `bash -c 'source scripts/lib/preflight.sh; <fn>'` with `PATH` overridden to stub `losetup`/`df`/`id`:
  - `test_check_root_fails_for_non_root`: stub `id -u` → `1000`; exit ≠ 0; stderr contains `ERROR: must run as root`.
  - `test_check_loop_devices_fails_when_losetup_fails`: stub `losetup` exits 1; stderr contains `ERROR: no loop devices`.
  - `test_check_disk_space_fails_below_min`: stub `df` reports 10 GB available; `check_disk_space /x 20` fails, stderr contains `need 20 GB`.
  - `test_check_disk_space_passes_at_min`: 20 GB → exit 0.
- [ ] **Step 2: Run** `wsl -d rocket-build -- python -m pytest tests/test_preflight.py -v` (the first run of `build.ps1 -SetupOnly` creates the distro). Expected: FAIL (file not found).
- [ ] **Step 3: Implement `scripts/lib/preflight.sh`.** Use `df --output=avail -BG <dir>`.
- [ ] **Step 4: Implement `scripts/setup-build-host.sh`:**
  - `pacman -Syu --noconfirm archiso base-devel git python-pytest python-yaml qemu-base edk2-ovmf ntfs-3g dosfstools`;
  - import and locally sign the CachyOS key (`pacman-key --recv-keys F3B607488DB35A47 --keyserver keyserver.ubuntu.com && pacman-key --lsign-key F3B607488DB35A47`);
  - install `cachyos-keyring` and `cachyos-mirrorlist` from `https://mirror.cachyos.org/repo/x86_64/cachyos/`;
  - create a non-root `builder` user for makepkg.
- [ ] **Step 5: Implement `build.ps1`** (with `-SetupOnly` and `-Clean` switches) and the `build.sh` skeleton, which sources preflight and runs all three checks.
- [ ] **Step 6: Run** `.\build.ps1 -SetupOnly`, then the pytest command. Expected: 4 passed.
  - Then `wsl -d rocket-build -u root -- bash build.sh --preflight-only`. Expected: `Preflight OK`.
  - If `check_loop_devices` fails on this machine, stop and report. It is the spec §14 risk; the fallback is a Hyper-V Arch VM build host and needs the user's input.
- [ ] **Step 7: Commit** `feat(build): WSL2 build host and preflight checks`; push.

### Task 2: archiso profile with package resolution test

**Files:**
- Create: `iso/profiledef.sh`, `iso/pacman.conf`, `iso/packages.x86_64`
- Create: `iso/efiboot/`, `iso/grub/` (copied from `/usr/share/archiso/configs/releng/`; `syslinux/` and BIOS entries are not copied)
- Test: `tests/test_profile.py`

**Interfaces:**
- Produces:
  - `profiledef.sh`: `iso_name="RocketOS"`, `iso_label="ROCKET_$(date +%Y%m)"`, `iso_publisher="Rocket OS"`, `iso_version="$(date +%Y.%m.%d)"`, `bootmodes=('uefi.grub')`, `airootfs_image_type="squashfs"`, `airootfs_image_tool_options=('-comp' 'zstd' '-Xcompression-level' '15' '-b' '1M')`.
  - `pacman.conf`: repos in order `[cachyos]`, `[core]`, `[extra]`, `[multilib]`, `[rocket]` (`Server = file:///var/tmp/rocket-work/repo`).
- Package list contents (spec §5.1, Phase 1 subset):
  - base: `base linux-cachyos linux-cachyos-headers linux-firmware amd-ucode btrfs-progs grub efibootmgr os-prober snapper grub-btrfs snap-pac zram-generator sbctl ntfs-3g dosfstools`
  - graphics: `mesa lib32-mesa vulkan-radeon lib32-vulkan-radeon libva-mesa-driver`
  - desktop: `plasma-desktop plasma-nm plasma-pa powerdevil kscreen bluedevil breeze-gtk dolphin konsole ark spectacle sddm sddm-kcm firefox networkmanager bluez bluez-utils pipewire pipewire-pulse wireplumber`
  - gaming: `steam`
  - installer and tooling: `calamares rocket-base arch-install-scripts mkinitcpio-archiso`
  - plus the releng live essentials kept: `archinstall` removed; `memtest86+-efi`; `edk2-shell` removed.

- [ ] **Step 1: Write failing tests** in `tests/test_profile.py`:
  - `test_bootmodes_uefi_only`: parse `profiledef.sh`; `bootmodes` contains only `uefi.*` entries.
  - `test_required_packages_present`: every package in the lists above is in `packages.x86_64`.
  - `test_no_duplicate_packages`
  - `test_no_banned_packages`: none of `baloo-widgets`, `kdeconnect`, `cups`, `avahi`, `modemmanager`, `archinstall`.
  - `test_pacman_conf_repo_order`: section order as above; `[multilib]` enabled.
  - `test_packages_resolve` (marker `network`): runs `pacman --config iso/pacman.conf -Sp --print-format %n $(packages minus rocket-*)`. Exit 0; on failure, the assertion message lists the unresolved names parsed from `error: target not found: X`.
- [ ] **Step 2: Run** `python -m pytest tests/test_profile.py -v`. Expected: FAIL.
- [ ] **Step 3:** Copy releng into `iso/`, then edit `profiledef.sh`, `pacman.conf` and `packages.x86_64` as specified. Delete `syslinux/` and the BIOS entries.
- [ ] **Step 4: Check the `calamares` package.** If `test_packages_resolve` reports `calamares` missing from `[cachyos]`, add `packages/calamares/PKGBUILD` (fetched from AUR `calamares`) to the local build in Task 4 and mark it as `rocket`-repo provided in the test.
- [ ] **Step 5: Run tests.** Expected: all pass.
- [ ] **Step 6: Commit** `feat(iso): archiso profile and package list`; push.

### Task 3: Live session overlay

**Files:**
- Create under `iso/airootfs/`:
  - `etc/hostname` (`rocket`)
  - `etc/locale.conf` (`LANG=en_US.UTF-8`), `etc/locale.gen` (en_US line uncommented)
  - `etc/sddm.conf.d/autologin.conf` (`[Autologin] User=rocket Session=plasma`)
  - `etc/sudoers.d/rocket-live` (`rocket ALL=(ALL) NOPASSWD: ALL`, mode 0440)
  - `etc/systemd/system/display-manager.service` → symlink `/usr/lib/systemd/system/sddm.service`
  - `etc/systemd/system/multi-user.target.wants/NetworkManager.service` → symlink
  - `etc/systemd/system/bluetooth.target.wants/bluetooth.service` → symlink
  - `etc/xdg/baloofilerc` (`[Basic Settings] Indexing-Enabled=false`)
  - `etc/passwd`, `etc/shadow`, `etc/group`, `etc/gshadow` entries for `rocket` (uid 1000, groups `wheel`, empty password `rocket::` in shadow)
  - `home/rocket/Desktop/install-rocket.desktop` (Exec `sudo -E calamares`, Name "Install Rocket OS")
- Modify: `iso/profiledef.sh` `file_permissions` for sudoers (0:0:440), shadow (0:0:400) and `/home/rocket` (1000:1000:750)
- Test: `tests/test_profile.py` (append)

**Interfaces:**
- Produces: the live user `rocket` (uid 1000) and the desktop launcher `install-rocket.desktop`. Task 6 removes the user and the launcher from the installed system.

- [ ] **Step 1: Write failing tests:**
  - `test_live_autologin_plasma`: autologin.conf has `User=rocket` and `Session=plasma`.
  - `test_display_manager_is_sddm`: symlink target ends with `sddm.service`.
  - `test_baloo_disabled`
  - `test_sudoers_permissions`: `file_permissions` contains `["/etc/sudoers.d/rocket-live"]="0:0:440"`.
  - `test_installer_launcher_present`
- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Create the overlay files.** Symlinks are committed as git symlinks. `build.sh` sets `core.symlinks`, and the repo adds a `.gitattributes` entry `iso/airootfs/** -text`. Because Windows git may check symlinks out as text files, `build.sh` rsyncs the repo into `/var/tmp/rocket-src` inside WSL and recreates the symlinks from `iso/symlinks.txt` (format `link -> target`, one per line) before running mkarchiso. Tests read `iso/symlinks.txt`, not the filesystem.
- [ ] **Step 4: Run tests.** Expected: pass.
- [ ] **Step 5: Commit** `feat(iso): live Plasma session with autologin`; push.

### Task 4: `rocket-base` package, ISO build and boot test

**Files:**
- Create: `packages/rocket-base/PKGBUILD`, which installs:
  - `/usr/lib/os-release-rocket` → `/etc/os-release` via `backup`/install hook. `NAME="Rocket OS"`, `ID=rocketos`, `ID_LIKE=arch`, `PRETTY_NAME="Rocket OS"`, `ANSI_COLOR="38;2;255;106;0"`, `HOME_URL="https://github.com/shahfahim/Rocket-An-user-friendly-OS-for-gaming"`.
  - `/etc/default/grub.d/rocket.cfg`: `GRUB_DISTRIBUTOR="Rocket OS"`, `GRUB_TIMEOUT=5`, `GRUB_DISABLE_OS_PROBER=false`, `GRUB_CMDLINE_LINUX_DEFAULT="quiet splash amd_pstate=active nowatchdog"`. (The Arch grub package sources `/etc/default/grub` only, so the PKGBUILD's `.install` appends `. /etc/default/grub.d/rocket.cfg` once.)
  - `/etc/snapper/config-templates/rocket` with the retention values from Global Constraints.
  - `/etc/xdg/baloofilerc` (moved here from Task 3 so it reaches the installed system; the Task 3 test is updated to check the package file).
- Modify: `build.sh` adds:
  - `build_packages` (makepkg as `builder` for each `packages/*/`, `repo-add /var/tmp/rocket-work/repo/rocket.db.tar.gz`);
  - `build_iso` (`mkarchiso -v -w /var/tmp/rocket-work/work -o out/ iso/`);
  - `checksum` (`sha256sum` → `.sha256`);
  - a `linux-zen` fallback: if `pacman -Sy` against `[cachyos]` fails, sed `linux-cachyos` → `linux-zen` in a temp copy of `packages.x86_64` and print `WARN: CachyOS unreachable, using linux-zen`.
- Create: `tests/boot/qemu-boot.sh <iso>`.
- Test: `tests/test_profile.py` (append), `tests/boot/qemu-boot.sh`

**Interfaces:**
- Consumes: Task 1 preflight, Task 2 profile, Task 3 overlay.
- Produces:
  - `out/RocketOS-<ver>-x86_64.iso` and `.sha256`;
  - `tests/boot/qemu-boot.sh <iso>`: exit 0 if the live system reaches `graphical.target` within 180 s.

- [ ] **Step 1: Write failing tests:**
  - `test_os_release_branding`: PKGBUILD source `os-release` contains `NAME="Rocket OS"` and `ID_LIKE=arch`.
  - `test_grub_defaults`: `rocket.cfg` has `GRUB_DISABLE_OS_PROBER=false` and `GRUB_TIMEOUT=5`.
  - `test_snapper_retention`: values `NUMBER_LIMIT="10"`, `TIMELINE_LIMIT_DAILY="7"`, `TIMELINE_LIMIT_HOURLY="0"`.
- [ ] **Step 2: Implement `qemu-boot.sh`.**
  - Command: `qemu-system-x86_64 -machine q35 -m 4G -smp 4 -bios /usr/share/edk2/x64/OVMF.4m.fd -cdrom <iso> -display none -serial file:$log -no-reboot` (plus `-enable-kvm` only if `/dev/kvm` exists).
  - The ISO's live kernel cmdline includes `console=ttyS0,115200 systemd.show_status=1`, added to `iso/grub/grub.cfg` and `iso/efiboot` entries.
  - Poll `$log` for `Reached target Graphical Interface` (pass) or `Kernel panic`/`emergency mode` (fail). Time out at 180 s with KVM, 900 s without.
- [ ] **Step 3: Run pytest.** Expected: FAIL. Implement the PKGBUILD and `build.sh` functions. Run pytest. Expected: pass.
- [ ] **Step 4: Build.** Run `.\build.ps1`. Expected: `out/RocketOS-*.iso` exists, size 2–4 GB, and `sha256sum -c` passes.
- [ ] **Step 5: Boot test.** Run `wsl -d rocket-build -u root -- bash tests/boot/qemu-boot.sh out/RocketOS-*.iso`. Expected: `PASS: reached graphical.target in <N>s`.
- [ ] **Step 6: Commit** `feat(build): rocket-base package, ISO build and QEMU boot test`; push. ISOs are not committed (`.gitignore`: `out/`).

### Task 5: Calamares branding and module sequence

**Files:**
- Create: `installer/calamares/settings.conf`
- Create: `installer/calamares/branding/rocket/branding.desc`, `logo.png`, `welcome.png` (generated: orange `#FF6A00` rocket glyph on dark `#121418`, created with ImageMagick in `build.sh` if absent, so no binary assets are committed), `show.qml`
- Modify: `iso/profiledef.sh` / `build.sh` copy `installer/calamares` → `airootfs/etc/calamares`
- Test: `tests/test_installer.py`

**Interfaces:**
- Produces: the `settings.conf` exec sequence, which Tasks 6–7 fill with module configs:
  - `show: welcome, locale, keyboard, partition, users, summary`
  - `exec: partition, mount, unpackfs, machineid, fstab, locale, keyboard, localecfg, users, displaymanager, networkcfg, hwclock, services-systemd, shellprocess@rocket-post, removeuser, initcpio, bootloader, shellprocess@rocket-grub, umount`
  - `show: finished`

- [ ] **Step 1: Write failing tests** (parse YAML with `yaml.safe_load`):
  - `test_exec_sequence_order`: `unpackfs` before `users`; `removeuser` after `users`; `bootloader` after `initcpio`; `shellprocess@rocket-grub` after `bootloader`; `umount` last.
  - `test_branding_name`: `branding.desc` `strings.productName == "Rocket OS"`.
  - `test_instances_declared`: `settings.conf` `instances` declares `rocket-post` and `rocket-grub` for module `shellprocess`.
- [ ] **Step 2: Run.** Expected: FAIL. **Step 3: Implement.** **Step 4: Run.** Expected: pass.
- [ ] **Step 5: Commit** `feat(installer): calamares branding and module sequence`; push.

### Task 6: Calamares partition, mount and system modules (dual-boot on btrfs)

**Files:**
- Create in `installer/calamares/modules/`:
  - `welcome.conf`: `requirements.check: [storage, ram, power, internet]`, `required: [storage, ram]`, `requiredStorage: 40`, `requiredRam: 4.0`.
  - `partition.conf`: `efi.mountPoint: /boot/efi`, `efi.recommendedSize: 300MiB`, `efi.minimumSize: 32MiB`, `userSwapChoices: [none]` (zram is used), `defaultFileSystemType: btrfs`, `availableFileSystemTypes: [btrfs]`, `initialPartitioningChoice: alongside`, `initialSwapChoice: none`, `enableLuksAutomatedPartitioning: true`.
  - `mount.conf`: `btrfsSubvolumes` `@`→`/`, `@home`→`/home`, `@snapshots`→`/.snapshots`, `@var_log`→`/var/log`, `@games`→`/games`; `mountOptions` for btrfs `defaultOptions: [defaults, noatime, compress=zstd:1]`; ESP options `[umask=0077]`.
  - `unpackfs.conf`: source `/run/archiso/bootmnt/arch/x86_64/airootfs.sfs`, `sourcefs: squashfs`, destination `""`; second entry copies `/run/archiso/bootmnt/arch/boot/x86_64/vmlinuz-linux-cachyos` → `/boot/`.
  - `users.conf`: `defaultGroups: [wheel, video, audio, input, games]`, `sudoersGroup: wheel`, `doAutologin: true`, `setRootPassword: false`, `passwordRequirements.minLength: 4`.
  - `removeuser.conf`: `username: rocket`.
  - `displaymanager.conf`: `displaymanagers: [sddm]`, `defaultDesktopEnvironment.executable: startplasma-wayland`, `desktopFile: plasma`.
  - `services-systemd.conf`: enable `NetworkManager`, `bluetooth`, `sddm`, `fstrim.timer`, `snapper-timeline.timer`, `snapper-cleanup.timer`, `grub-btrfsd`.
  - `initcpio.conf`: `kernel: linux-cachyos`.
  - `shellprocess-rocket-post.conf` (`dontChroot: false`, run in target):
    - `rm -f /etc/sudoers.d/rocket-live /etc/sddm.conf.d/autologin.conf`
    - `pacman -Rns --noconfirm calamares mkinitcpio-archiso`
    - `rm -f /home/*/Desktop/install-rocket.desktop`
    - `snapper --no-dbus -c root create-config -t rocket /` (with `@snapshots` already mounted: delete the auto-created `/.snapshots` subvolume first, then remount, per the Arch wiki "snapper with @snapshots" procedure)
    - `cp /usr/share/zram-generator/... ` → `/etc/systemd/zram-generator.conf` with `zram-size = ram / 2`, `compression-algorithm = zstd`.
- Test: `tests/test_installer.py` (append)

**Interfaces:**
- Consumes: Task 5's exec sequence and instance names.
- Produces: an installed target with btrfs subvolumes and snapper config `root` (Task 7 relies on both).

- [ ] **Step 1: Write failing tests:**
  - `test_alongside_default`
  - `test_btrfs_only`
  - `test_subvolumes_exact` (the five pairs above, exact)
  - `test_esp_not_formatted_by_default`: `partition.conf` has no `efi.forceFormat` or sets it false.
  - `test_no_swap_partition`
  - `test_live_artifacts_removed`: the `rocket-post` script contains `calamares`, `rocket-live`, `autologin.conf` removals.
  - `test_snapper_uses_rocket_template`
- [ ] **Step 2: Run.** Expected: FAIL. **Step 3: Implement.** **Step 4: Run.** Expected: pass.
- [ ] **Step 5: Commit** `feat(installer): dual-boot btrfs partitioning and system config`; push.

### Task 7: Bootloader with Windows entry and snapshots menu

**Files:**
- Create: `installer/calamares/modules/bootloader.conf`: `efiBootLoader: grub`, `grubInstall: grub-install`, `grubMkconfig: grub-mkconfig`, `grubCfg: /boot/grub/grub.cfg`, `efiBootloaderId: RocketOS`, `installEFIFallback: false` (never overwrite Windows' fallback `\EFI\BOOT\BOOTX64.EFI`).
- Create: `installer/calamares/modules/shellprocess-rocket-grub.conf` (in target):
  - Write `/etc/grub.d/40_custom` with a `menuentry "Windows Boot Manager (fallback)"`. It searches `--fs-uuid` of the ESP (resolved at install time via `findmnt -no UUID /boot/efi`) and runs `chainloader /EFI/Microsoft/Boot/bootmgfw.efi`. It is only added when that file exists on the ESP.
  - `grub-mkconfig -o /boot/grub/grub.cfg`
  - `systemctl enable grub-btrfsd`
- Create: `packages/rocket-base/files/grub-btrfs-config`, which sets `GRUB_BTRFS_SUBMENUNAME="Rocket snapshots"` (installed to `/etc/default/grub-btrfs/config`).
- Test: `tests/test_installer.py` (append)

**Interfaces:**
- Consumes: Task 4's `/etc/default/grub.d/rocket.cfg` and Task 6's snapper config.

- [ ] **Step 1: Write failing tests:**
  - `test_bootloader_grub_no_fallback_overwrite`: `installEFIFallback` is false.
  - `test_windows_fallback_entry`: the `rocket-grub` script writes `chainloader /EFI/Microsoft/Boot/bootmgfw.efi` guarded by `[ -f /boot/efi/EFI/Microsoft/Boot/bootmgfw.efi ]`.
  - `test_snapshot_submenu_name`: grub-btrfs config contains `GRUB_BTRFS_SUBMENUNAME="Rocket snapshots"`.
- [ ] **Step 2: Run.** Expected: FAIL. **Step 3: Implement.** **Step 4: Run.** Expected: pass.
- [ ] **Step 5:** Rebuild the ISO (`.\build.ps1`) and re-run `qemu-boot.sh`. Expected: PASS.
- [ ] **Step 6: Commit** `feat(installer): GRUB with Windows fallback and Rocket snapshots menu`; push.

### Task 8: VM dual-boot install test and real-hardware checklist

**Files:**
- Create: `tests/install/make-fake-windows-disk.sh <out.qcow2>`:
  - 120 GB qcow2, GPT;
  - partition 1: 100 MiB FAT32 ESP containing `EFI/Microsoft/Boot/bootmgfw.efi` (copy of OVMF's `Shell.efi`, renamed, so the GRUB entry is testable);
  - partition 2: 16 MiB MSR;
  - partition 3: rest NTFS (`mkfs.ntfs -f -L Windows`) with a 1 GB filler file.
  - Uses `qemu-nbd` (fallback: `losetup` on a raw image, then `qemu-img convert`).
- Create: `tests/install/run-install-vm.sh <iso> <disk>`: QEMU with the GUI shown through WSLg (`-display gtk`), `-m 6G`, OVMF vars copied per run.
- Create: `docs/testing/phase1-checklist.md`

**Interfaces:**
- Consumes: the Task 4/7 ISO.

- [ ] **Step 1: Write the checklist** with checkboxes and expected results.
  - **VM:**
    1. Live desktop appears with autologin.
    2. Install with "Install alongside" and the slider; the NTFS partition shrinks.
    3. Reboot.
    4. GRUB shows `Rocket OS`, `Rocket snapshots`, `Windows Boot Manager (fallback)`.
    5. Rocket boots to SDDM, then Plasma, as the created user.
    6. `findmnt /` shows `subvol=/@` and `compress=zstd:1`.
    7. `snapper list` works.
    8. `sudo pacman -S --noconfirm htop` creates pre/post snapshots.
    9. After `grub-mkconfig`, the snapshot submenu lists them.
    10. `pacman -Q calamares` returns "not found".
    11. The live user `rocket` doesn't exist.
    12. Baloo is off (`balooctl6 status` → disabled).
  - **Negative test:** make a second fake disk whose NTFS partition is filled to 100%. Confirm that Calamares disables "Install alongside" (or shows that not enough space is available) and that the disk's partition table is byte-identical before and after (`sgdisk --backup` compared with `cmp`).
  - **Real hardware (live USB only, no install):** Wi-Fi connects; Bluetooth pairs; speakers and headphone jack; touchpad gestures; brightness keys; suspend/resume; `vulkaninfo --summary` shows `AMD Radeon Graphics (RADV RENOIR)`; Steam installs and launches.
- [ ] **Step 2:** Implement both scripts. Run `make-fake-windows-disk.sh`. Expected: `fdisk -l` shows 3 partitions with the types above.
- [ ] **Step 3: Run the VM install** following the checklist and record the results in the checklist file. Any failure goes back to the owning task (6 or 7) as a fix with a regression test.
- [ ] **Step 4: Commit** `test: VM dual-boot install harness and Phase 1 checklist`; push.
- [ ] **Step 5: Hand off to the user.** Give them the ISO path, the Rufus instructions and the real-hardware checklist. The real install on the laptop is done by the user, never by an agent.
