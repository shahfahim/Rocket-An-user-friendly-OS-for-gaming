# Rocket OS: Design Spec

- **Date:** 2026-10-08
- **Status:** Draft, awaiting review
- **Owner:** Nabil

## 1. Purpose

Rocket OS is a personal, Arch Linux–based gaming operating system for one machine. It should:

- Give games as much CPU, GPU and RAM as possible, with minimal background activity.
- Be easy to use: console-like Game Mode by default and a familiar Windows-style desktop.
- Replace AMD Adrenalin (Windows-only) with an equivalent control panel, **Rocket Control**.
- Include **Rocket Cheat**, a Cheat Engine–style memory editor for single-player/offline games.
- Be secure enough for daily use without getting in the way.
- Ship as a bootable live ISO that installs alongside the existing Windows 11 (dual-boot).

### What the user asked for vs. what we decided

| User requirement | Design decision |
|---|---|
| Optimized, focused while gaming | Gamescope Game Mode session, CachyOS kernel, gamemode, minimal services |
| Enough security | Firewall, AppArmor, Secure Boot, optional LUKS, password-gated admin actions |
| User friendly | Game Mode default, KDE Plasma desktop laid out like Windows, Calamares installer |
| Minimal background apps | Fixed whitelist of services; idle RAM target < 700 MB in Game Mode |
| Panel for FPS, cores, etc. | Rocket Control (Section 6) |
| Pre-installed AMD Adrenalin | Not possible on Linux; Rocket Control provides the equivalent features |
| Universal cheat mode | Rocket Cheat (Section 7), single-player/offline only |
| Bootable, installable | archiso live ISO + Calamares "Install alongside Windows" |

### Non-goals

- Supporting hardware other than the target laptop (no NVIDIA/Intel GPU work, no generic hardware matrix).
- Public distribution or a support infrastructure.
- Running games with kernel-level anti-cheat that blocks Linux (Valorant, Fortnite, some CoD). Windows stays installed for these.
- Bypassing anti-cheat or cheating in online multiplayer.
- Any feature for obtaining or cracking games.

## 2. Target hardware

| Component | Value |
|---|---|
| Device | ASUS Vivobook 14, model M1405YA (laptop) |
| CPU | AMD Ryzen 7 7730U: Zen 3, 8C/16T, 15 W nominal TDP |
| GPU | Integrated Radeon Vega 8 (GCN 5), shares system RAM |
| RAM | 16 GB |
| Storage | 1 TB Micron 2400 NVMe SSD (single drive, Windows 11 installed) |
| Firmware | UEFI, Secure Boot likely enabled; BitLocker device encryption possibly enabled |

**Performance expectation:** the main FPS lever is raising sustained package power (TDP) from 15 W to about 25–28 W on AC. Light and older titles should run at 720p–1080p (with FSR where useful); recent AAA titles at low settings or not at all.

## 3. Architecture overview

```
┌───────────────────────── Boot ─────────────────────────┐
│ GRUB: Rocket OS (default, 5 s) │ Rocket snapshots │ Windows │
└────────────────────────────────────────────────────────┘
                     │
            auto-login (SDDM)
                     │
     ┌───────────────┴────────────────┐
     ▼                                ▼
 Game Mode (default)            Desktop Mode
 gamescope + Steam Big Picture   KDE Plasma (trimmed)
     │                                │
     └──────── shared layers ─────────┘
 Rocket apps : rocket-control, rocket-cheat, rocket-update
 Daemon      : rocketd (root, D-Bus, polkit)
 Gaming      : Steam, Proton-GE, Heroic, Lutris, Wine, gamemode, MangoHud
 Graphics    : Mesa RADV (ACO), VA-API
 Kernel      : linux-cachyos (BORE), amd-pstate=active
 Storage     : btrfs (zstd) + snapper, zram swap
 Security    : firewalld, AppArmor, sbctl, optional LUKS
```

### Session switching

- **Game Mode** is the default session. Steam's "Switch to Desktop" option switches to Plasma, using a session-switch script modeled on SteamOS/ChimeraOS (`rocket-session-select`).
- A "Return to Game Mode" desktop icon in Plasma switches back.
- The chosen default persists in `/etc/rocket/session.conf`.

## 4. Repository layout

```
build.ps1                 Windows entry point: prepares WSL2 Arch and runs build.sh
build.sh                  Builds local packages, then runs mkarchiso
iso/                      archiso profile (releng-derived)
  packages.x86_64
  pacman.conf             includes CachyOS repos + local [rocket] repo
  profiledef.sh
  airootfs/               live-system overlay (configs, systemd units, branding)
packages/                 PKGBUILDs for rocket-* packages
  rocket-settings/        system tuning config (sysctl, udev, services, kernel cmdline)
  rocket-session/         gamescope session + session switching
  rocket-control/
  rocket-cheat/
  rocket-branding/        GRUB/Plymouth/SDDM/Plasma themes, wallpapers
apps/
  rocketd/                Python D-Bus daemon (root)
  control/                Rocket Control Qt app
  cheat/                  Rocket Cheat Qt app + memory engine
installer/                Calamares settings, modules, branding
tests/                    pytest suites + QEMU boot/install tests
docs/
```

## 5. Base system

### 5.1 Packages (summary)

- **Base:** `base`, `linux-cachyos`, `linux-cachyos-headers`, `linux-firmware`, `amd-ucode`, `btrfs-progs`, `grub`, `efibootmgr`, `os-prober`, `snapper`, `grub-btrfs`, `snap-pac`, `zram-generator`, `sbctl`.
- **Graphics:** `mesa`, `lib32-mesa`, `vulkan-radeon`, `lib32-vulkan-radeon`, `libva-mesa-driver`.
- **Desktop:** minimal Plasma set (`plasma-desktop`, `plasma-nm`, `plasma-pa`, `powerdevil`, `kscreen`, `bluedevil`, `dolphin`, `konsole`, `ark`, `spectacle`, `sddm`), plus `firefox`.
- **Gaming:** `steam`, `gamescope`, `gamemode`, `lib32-gamemode`, `mangohud`, `lib32-mangohud`, `proton-ge-custom`, `heroic-games-launcher`, `lutris`, `wine-staging`, `winetricks`, `protontricks`.
- **Hardware control:** `ryzenadj`, `asusctl` (fan/platform profiles, battery limit).
- **Cheat tooling:** `pince` (advanced users).
- **Security:** `firewalld`, `apparmor`.
- **Installer (live only):** `calamares`.

### 5.2 Tuning (`rocket-settings` package)

| Area | Setting |
|---|---|
| Kernel cmdline | `amd_pstate=active split_lock_detect=off nowatchdog quiet splash apparmor=1 lsm=landlock,lockdown,yama,integrity,apparmor,bpf` |
| Memory | zram (size = RAM/2, zstd); `vm.swappiness=150`; `vm.max_map_count=2147483642`; MGLRU on |
| Disk | btrfs `compress=zstd:1,noatime`; NVMe scheduler `none` via udev; `fstrim.timer` |
| GPU | RADV/ACO defaults; shared shader cache; installer shows guidance for setting UMA frame buffer to 4 GB in the BIOS (if exposed) |
| gamemode | `renice=10`, `ioprio=0`, CPU governor/EPP switched to performance; start/end hooks pause `snapper-timeline.timer` and `rocket-update.timer` |
| Boot | Plymouth splash; disable `NetworkManager-wait-online`, `systemd-networkd`, etc. Target: < 15 s from GRUB to Game Mode |

### 5.3 Service whitelist

Enabled: `NetworkManager`, `bluetooth` (socket/on demand), `pipewire`/`wireplumber` (user), `rocketd`, `asusd`, `firewalld`, `apparmor`, `snapper-timeline.timer`, `snapper-cleanup.timer`, `fstrim.timer`, `rocket-update.timer`, `sddm`.

Disabled or not installed: Baloo file indexing, CUPS (installable later), avahi, ModemManager, KDE Connect, KDE online accounts, telemetry of any kind.

**Acceptance:** idle RAM use < 700 MB in Game Mode (measured with `free` after 2 minutes idle) and < 1.2 GB in Desktop Mode.

## 6. Rocket Control

### 6.1 Components

- **rocketd:** a Python service running as root on the system D-Bus as `org.rocketos.Control1`.
  - Every method validates its input against a fixed range table and rejects anything else.
  - Actions that change system state require the polkit action `org.rocketos.control.apply`. It is allowed without a password for the active local user, except for the Cheat Mode method (Section 7.2).
- **rocket-control:** a PySide6 app running as the user. Talks only to rocketd over D-Bus and never writes to sysfs itself.
- **rocket-run:** a wrapper script used as Steam launch options (`rocket-run %command%`). It applies the game's profile through rocketd, launches the game under `gamemoderun` with MangoHud configured, and restores defaults on exit (including crashes, via a `trap`).

### 6.2 Features and allowed ranges

| Tab | Control | Backend | Allowed values |
|---|---|---|---|
| Dashboard | Live FPS, CPU/GPU %, clocks, temps, package power, RAM/VRAM | MangoHud log socket, sysfs hwmon, `ryzenadj --info` | read-only |
| Dashboard | Cheat Mode quick toggle | rocketd → rocket-cheat-helper | on/off |
| Performance | Silent / Balanced / Turbo | ryzenadj (STAPM/fast/slow limits) + `asusctl profile` | Silent ≈10 W, Balanced 15 W, Turbo 25–28 W **on AC only**; falls back to Balanced when unplugged |
| CPU | Active cores | `/sys/devices/system/cpu/cpuN/online` | 2–8 physical cores (CPU0 always online) |
| CPU | SMT | `/sys/devices/system/cpu/smt/control` | on/off |
| CPU | Governor / EPP | amd-pstate sysfs | `performance`/`powersave` × EPP values |
| CPU | Max clock cap | `scaling_max_freq` | 1.4 GHz to hardware max |
| GPU | Performance level | `power_dpm_force_performance_level` | auto/low/high/manual |
| GPU | Clock range (manual) | `pp_od_clk_voltage` if exposed, otherwise `pp_dpm_sclk` level masks | hardware-reported range only |
| GPU | FSR upscaling, sharpness | gamescope args (Game Mode) | on/off, sharpness 0–20 |
| Display & FPS | FPS cap | gamescope `-r`/Steam limiter in Game Mode; MangoHud `fps_limit` in Desktop Mode | 30/40/45/60/unlimited/custom 20–240 |
| Display & FPS | VSync | MangoHud `vsync` / gamescope | on/off/adaptive |
| Display & FPS | Overlay style | MangoHud preset | off/minimal/full |
| Game Profiles | Per-game overrides of any setting above | JSON in `~/.config/rocket/profiles/<appid-or-exe>.json` | as above |
| Battery | Charge limit | `asusctl -c` | 60–100 % |
| System | Snapshot list + "Restore this snapshot", update status | `snapper` via rocketd | existing snapshot IDs only |

**Out of scope:** undervolting/voltage curves and custom fan curves.

### 6.3 Access

- Desktop Mode: a start menu entry and a tray icon.
- Game Mode: a non-Steam library tile (added on first boot), and **Super+R** opens it on top of the running game through gamescope's focus handling.
- On first boot, `rocket-run %command%` is set as the default launch option for installed Steam games. Users can opt out per game.

### 6.4 Persistence

- System defaults: `/etc/rocket/control.json`, written only by rocketd.
- User profiles: `~/.config/rocket/`.
- On boot, rocketd re-applies the saved defaults.

## 7. Rocket Cheat

### 7.1 Components

- **rocket-cheat:** a PySide6 app running as the user.
- **rocket-cheat-helper:** the memory engine.
  - Written in Python with a small C extension for fast scanning.
  - Uses `process_vm_readv`/`process_vm_writev` and `/proc/<pid>/maps`.
  - Runs only while Cheat Mode is on.
  - Talks to the app over a Unix socket that only the logged-in user can access (`/run/rocket/cheat-<uid>.sock`).

### 7.2 Cheat Mode

- **Off by default.** The helper isn't running, and the system keeps Yama `ptrace_scope=1`, so no ordinary process can read another's memory.
- **Turning it on:**
  - Ways to toggle: the switch in Rocket Cheat, the Rocket Control Dashboard toggle, or **Super+C**.
  - rocketd's `EnableCheatMode` method requires polkit `auth_admin_keep`, so the user's password is asked for every time.
  - rocketd then starts `rocket-cheat-helper@<uid>.service` with `AmbientCapabilities=CAP_SYS_PTRACE`, running as the user.
- **Turning it off:** the same toggle stops the service. It is never started at boot, so a reboot always turns it off.
- **Indicator:** a 🎯 indicator in the MangoHud overlay and the KDE tray while it's on.

### 7.3 Features

- **Game picker:** lists processes that are Wine/Proton children or native games, with the game's name and icon (from the Steam appid, `.exe` name or `.desktop` file).
- **Scan types:**
  - exact value, increased, decreased, changed, unchanged, unknown initial value;
  - value types int8/16/32/64, float, double, UTF-8/UTF-16 string.
- **Cheat list:** name, address, type, value. You can edit values, freeze them (the helper rewrites the value every 50 ms) and delete entries.
- **Hotkeys:**
  - global hotkeys through the KDE global shortcuts / evdev listener in the helper;
  - actions: toggle freeze, or set a value.
- **Tables:** saved automatically to `~/.config/rocket/cheats/<game-id>.json` and reloaded when the same game is attached. Addresses are stored as module + offset so they survive ASLR when possible.
- **Advanced:** a "Open in PINCE" button for pointer scans and debugging.

### 7.4 Guardrail

The helper refuses to attach, and explains why, if the target process has loaded a known online anti-cheat module. The list covers EasyAntiCheat, BattlEye, nProtect GameGuard, Ricochet and Vanguard, matched by module names in `/proc/<pid>/maps`. The list lives in `/usr/share/rocket/anticheat.txt`.

### 7.5 Out of scope (v1)

Importing Cheat Engine `.CT` files, Auto Assembler scripts, speedhack.

## 8. Security

- **firewalld:** default zone `drop` for incoming traffic, with services allowed for Steam Remote Play and Steam LAN, and DHCP/mDNS client.
- **AppArmor:** enabled with the default profiles.
- **Secure Boot:**
  - The installer offers to enroll Rocket keys with `sbctl` (with Microsoft keys kept, `sbctl enroll-keys -m`, so Windows still boots).
  - The kernel and GRUB are signed automatically via the sbctl pacman hook.
  - If the user skips this, they are told to disable Secure Boot in the BIOS.
- **LUKS:** optional full-disk encryption checkbox in Calamares for the Rocket partition.
- **Authentication:** the user password is required for sudo, package installs and Cheat Mode. Auto-login applies only to the desktop session.
- **No telemetry.**

## 9. Updates and recovery

- **rocket-update:**
  - A timer checks daily and a Plasma notification offers "Install".
  - Updates never run while gamemode is active or in Game Mode.
  - Uses `pacman -Syu` through rocketd.
- **snap-pac:** takes btrfs pre/post snapshots around every pacman transaction.
- **grub-btrfs:** adds a "Rocket snapshots" submenu so you can boot any snapshot. `snapper rollback` is available from Rocket Control → System → "Restore this snapshot".
- **Kernel hold-back:** rocket-update holds `linux-cachyos` until the repo version has been published for at least 3 days.
- **Snapshot retention:** 10 pre/post pairs, 7 daily, 0 hourly.

## 10. Installation (dual-boot)

### 10.1 Before installing (shown in the live session's "Before you install" screen)

- Back up personal files.
- Save the BitLocker recovery key, or suspend/turn off BitLocker.
- Turn off Windows Fast Startup.
- Make sure there is at least 150 GB of free space on C: (suggested Rocket size: 300 GB or more).

### 10.2 Flow

1. Flash the ISO with Rufus or Ventoy.
2. Boot the USB: press ESC at the ASUS logo.
3. The live session boots into Desktop Mode with a "Welcome" app offering "Try" or "Install Rocket OS".
4. Calamares:
   - language, keyboard, timezone;
   - partitioning: **"Install alongside"** with a resize slider (default 300 GB), reusing the existing EFI partition;
   - btrfs subvolumes `@`, `@home`, `@snapshots`, `@var_log`, `@games`;
   - optional LUKS;
   - user and password;
   - Secure Boot key enrollment step;
   - install.
5. Reboot. GRUB, with os-prober enabled, lists Rocket OS, Rocket snapshots and Windows Boot Manager.

### 10.3 Failure handling

- If Calamares cannot shrink NTFS (BitLocker on or a dirty filesystem), it stops **before writing anything** and tells the user to suspend BitLocker or run `chkdsk` in Windows.
- If no Windows boot entry is detected after install, a GRUB fallback entry chainloads `\EFI\Microsoft\Boot\bootmgfw.efi`.

## 11. Build system

- `build.ps1` (Windows):
  - checks WSL2;
  - imports an Arch Linux WSL distro named `rocket-build` if it doesn't exist (from the official `archlinux` WSL image);
  - runs `build.sh` inside it.
- `build.sh`:
  - installs `archiso` and `base-devel`;
  - adds the CachyOS repos;
  - builds `packages/*` with `makepkg` into a local repo `out/repo/`;
  - runs `mkarchiso -v -w /tmp/rocket-work -o out/ iso/`.
- **Output:** `out/RocketOS-<YYYY.MM.DD>-x86_64.iso`, about 3 GB, plus a `.sha256` file.

## 12. Testing

| Target | Method | Pass criteria |
|---|---|---|
| rocketd validation | pytest, sysfs paths redirected to a temp dir | every out-of-range value is rejected; valid values are written correctly; Turbo is refused on battery |
| rocket-run | pytest with a fake game command | profile applied before launch; defaults restored after a normal exit and after SIGKILL of the game |
| Cheat engine | pytest against a C test program with known int/float values | scan → narrow → write → freeze works; refuses PIDs with anti-cheat module names; refuses when Cheat Mode is off |
| ISO boot | QEMU (OVMF UEFI) in WSL2, scripted | reaches SDDM/live session within 120 s; `systemctl --failed` is empty |
| Install | QEMU with a 120 GB disk pre-populated with a fake EFI + NTFS partition | "Install alongside" completes; GRUB shows both entries; installed system boots |
| Real hardware | Manual checklist on the live USB | Wi-Fi, Bluetooth, audio, touchpad, brightness, suspend/resume, Vega 8 Vulkan (`vkcube`), ryzenadj readings |

## 13. Delivery order

1. **Bootable base:** archiso profile, CachyOS kernel, Plasma, Steam, Calamares dual-boot install, snapshots. *Milestone: installable OS.*
2. **Tuning and Game Mode:** `rocket-settings`, `rocket-session`, service whitelist, security baseline.
3. **Rocket Control:** rocketd, Qt app, rocket-run, profiles.
4. **Rocket Cheat:** helper, Cheat Mode, Qt app, guardrail.
5. **Polish:** branding, welcome app, rocket-update, first-boot setup.

Each phase gets its own implementation plan and ends with a working, testable ISO.

## 14. Risks

| Risk | Mitigation |
|---|---|
| WSL2 cannot run `mkarchiso` (loop devices, mount privileges) | Run build in WSL2 as root with `--privileged`-equivalent setup; fallback: a small Arch VM (Hyper-V) used as the build host |
| ryzenadj blocked on newer firmware / Secure Boot lockdown | Lockdown integrity mode may block `/dev/mem` access. ryzenadj uses the `ryzen_smu` kernel module, which must be signed with our sbctl key. Fallback: `asusctl` platform profiles only |
| Rolling-release breakage | snap-pac snapshots + boot-to-snapshot + kernel hold-back |
| BitLocker blocks resize | Pre-install checklist + Calamares stops before any write |
| CachyOS repo availability | Fall back to the stock Arch `linux-zen` kernel if the CachyOS repos are unreachable at build time |
