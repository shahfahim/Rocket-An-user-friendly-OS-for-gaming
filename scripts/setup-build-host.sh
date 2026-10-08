#!/bin/bash
# One-time setup of the rocket-build WSL distro (Arch Linux). Run as root.
set -euo pipefail

MARKER=/var/lib/rocket-build/ready
CACHYOS_KEY=F3B607488DB35A47
CACHYOS_REPO=https://mirror.cachyos.org/repo/x86_64/cachyos

if [[ -f $MARKER ]]; then
    echo "Build host already set up."
    exit 0
fi

pacman-key --init
pacman-key --populate archlinux
pacman -Syu --noconfirm --needed \
    archiso base-devel git rsync python python-pytest python-yaml \
    qemu-base edk2-ovmf ntfs-3g dosfstools gptfdisk imagemagick ttf-dejavu \
    qemu-ui-gtk edk2-shell ntfsprogs mtools

# CachyOS repository keys and mirrorlist (kernel + calamares come from there).
pacman-key --recv-keys "$CACHYOS_KEY" --keyserver keyserver.ubuntu.com
pacman-key --lsign-key "$CACHYOS_KEY"
tmp=$(mktemp -d)
for pkg in cachyos-keyring cachyos-mirrorlist; do
    file=$(curl -fsSL "$CACHYOS_REPO/" | grep -oE "\"$pkg-[0-9][^\"]*\.pkg\.tar\.zst\"" | tr -d '"' | sort -V | tail -n1)
    [[ -n $file ]] || { echo "ERROR: could not find $pkg on $CACHYOS_REPO" >&2; exit 1; }
    curl -fsSL -o "$tmp/$file" "$CACHYOS_REPO/$file"
done
pacman -U --noconfirm "$tmp"/*.pkg.tar.zst
rm -rf "$tmp"

# Unprivileged user for makepkg.
id builder &>/dev/null || useradd -m builder
echo 'builder ALL=(ALL) NOPASSWD: /usr/bin/pacman' > /etc/sudoers.d/builder
chmod 440 /etc/sudoers.d/builder

mkdir -p "$(dirname "$MARKER")"
touch "$MARKER"
echo "Build host ready."
