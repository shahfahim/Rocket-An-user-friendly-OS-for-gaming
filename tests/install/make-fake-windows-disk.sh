#!/bin/bash
# Creates a raw disk image laid out like a Windows 11 install, for testing
# "Install alongside" in a VM. Run as root.
# Usage: make-fake-windows-disk.sh <out.img> [size=100G] [filler_mb=1024]
#   p1  100 MiB  EFI System (FAT32) with EFI/Microsoft/Boot/bootmgfw.efi (an EFI shell)
#   p2   16 MiB  Microsoft reserved
#   p3  rest     NTFS "Windows" with a filler file
set -euo pipefail

out=${1:?usage: make-fake-windows-disk.sh <out.img> [size] [filler_mb]}
size=${2:-100G}
filler_mb=${3:-1024}
shell_efi=/usr/share/edk2-shell/x64/Shell.efi

rm -f "$out"
truncate -s "$size" "$out"
sgdisk --zap-all \
    -n1:0:+100M -t1:EF00 -c1:"EFI system partition" \
    -n2:0:+16M  -t2:0C01 -c2:"Microsoft reserved partition" \
    -n3:0:0     -t3:0700 -c3:"Basic data partition" \
    "$out" >/dev/null

dev=$(losetup -fP --show "$out")
mnt=$(mktemp -d)
cleanup() {
    mountpoint -q "$mnt" && umount "$mnt"
    rmdir "$mnt"
    losetup -d "$dev"
}
trap cleanup EXIT

# Partition device nodes can appear a moment after losetup -P.
for _ in $(seq 50); do [[ -b ${dev}p3 ]] && break; sleep 0.1; done

mkfs.fat -F32 -n EFI "${dev}p1" >/dev/null
mount "${dev}p1" "$mnt"
install -D -m644 "$shell_efi" "$mnt/EFI/Microsoft/Boot/bootmgfw.efi"
umount "$mnt"

start=$(cat "/sys/class/block/$(basename "${dev}p3")/start")
mkfs.ntfs -f -q -L Windows -p "$start" -H 255 -S 63 "${dev}p3"
mount -t ntfs3 "${dev}p3" "$mnt" 2>/dev/null || ntfs-3g "${dev}p3" "$mnt"
dd if=/dev/urandom of="$mnt/filler.bin" bs=1M count="$filler_mb" status=none
umount "$mnt"

echo "Created $out ($size): ESP + MSR + NTFS with ${filler_mb} MiB filler"
