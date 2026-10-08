#!/bin/bash
# Builds the Rocket OS ISO. Runs inside the rocket-build WSL distro as root.
# Usage: build.sh [--preflight-only] [--clean]
set -euo pipefail

REPO=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
ROCKET_WORK=/var/tmp/rocket-work
SRC=$ROCKET_WORK/src          # staged copy of the repo (ext4, real symlinks)
REPO_DIR=$ROCKET_WORK/repo    # local [rocket] pacman repo, see iso/pacman.conf
MIN_FREE_GB=20
CACHYOS_DB_URL=https://mirror.cachyos.org/repo/x86_64/cachyos/cachyos.db

# shellcheck source=scripts/lib/preflight.sh
source "$REPO/scripts/lib/preflight.sh"
# shellcheck source=scripts/lib/stage.sh
source "$REPO/scripts/lib/stage.sh"

preflight_only=0 clean=0
for arg in "$@"; do
    case $arg in
        --preflight-only) preflight_only=1 ;;
        --clean) clean=1 ;;
        *) echo "Unknown argument: $arg" >&2; exit 2 ;;
    esac
done

mkdir -p "$ROCKET_WORK"
check_root
check_loop_devices
check_disk_space "$ROCKET_WORK" "$MIN_FREE_GB"
echo "Preflight OK"
[[ $preflight_only -eq 1 ]] && exit 0

if [[ $clean -eq 1 ]]; then
    rm -rf "${ROCKET_WORK:?}/work"
fi

stage_source() {
    echo "==> Staging source into $SRC"
    rm -rf "$SRC"
    mkdir -p "$SRC"
    rsync -a --delete --exclude .git --exclude out --exclude .superpowers "$REPO/" "$SRC/"
    apply_symlinks "$SRC/iso/symlinks.txt" "$SRC/iso/airootfs"
    if [[ -d $SRC/installer/calamares ]]; then
        mkdir -p "$SRC/iso/airootfs/usr/share/rocket/calamares"
        cp -r "$SRC/installer/calamares/." "$SRC/iso/airootfs/usr/share/rocket/calamares/"
        make_branding_images "$SRC/iso/airootfs/usr/share/rocket/calamares/branding/rocket"
    fi
    if ! curl -fsI --max-time 15 "$CACHYOS_DB_URL" >/dev/null; then
        echo "WARN: CachyOS unreachable, using linux-zen" >&2
        swap_kernel "$SRC/iso" linux-cachyos linux-zen
        grep -rl 'linux-cachyos' "$SRC/iso/airootfs/usr/share/rocket/calamares" 2>/dev/null \
            | xargs -r sed -i 's/linux-cachyos/linux-zen/g'
    fi
}

build_packages() {
    echo "==> Building local packages"
    mkdir -p "$REPO_DIR"
    rm -f "$REPO_DIR"/*
    chown -R builder: "$SRC/packages"
    local pkg
    for pkg in "$SRC"/packages/*/; do
        (cd "$pkg" && sudo -u builder makepkg -f --cleanbuild --syncdeps --noconfirm --nocheck)
        cp "$pkg"/*.pkg.tar.zst "$REPO_DIR/"
    done
    repo-add -q "$REPO_DIR/rocket.db.tar.gz" "$REPO_DIR"/*.pkg.tar.zst
}

build_iso() {
    echo "==> Building ISO"
    rm -rf "$ROCKET_WORK/work" "$ROCKET_WORK/iso-out"
    mkarchiso -v -w "$ROCKET_WORK/work" -o "$ROCKET_WORK/iso-out" "$SRC/iso"
    # build.ps1 copies the ISO to out/ from the Windows side (large /mnt writes can fail).
    (cd "$ROCKET_WORK/iso-out" && sha256sum RocketOS-*.iso > SHA256SUMS)
    echo "==> Done: $(ls "$ROCKET_WORK"/iso-out/RocketOS-*.iso)"
}

stage_source
build_packages
build_iso
