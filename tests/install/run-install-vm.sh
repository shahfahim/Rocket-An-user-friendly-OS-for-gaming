#!/bin/bash
# Boots the ISO in a UEFI VM with a fake-Windows disk attached, for install testing.
# Usage: run-install-vm.sh <iso|--disk-only> <disk.img> [--headless]
#   <iso>        boot the live ISO (install flow)
#   --disk-only  boot the installed disk (post-install checks)
#   --headless   no window; drive it through the QMP socket (tests/install/qmp.py)
# State (OVMF vars, QMP socket, serial log) lives in /var/tmp/rocket-vm/.
set -euo pipefail

iso=${1:?usage: run-install-vm.sh <iso|--disk-only> <disk.img> [--headless]}
disk=${2:?missing disk image}
mode=${3:-}

state=/var/tmp/rocket-vm
mkdir -p "$state"
# One set of NVRAM vars per disk, so GRUB's boot entry survives reboots.
vars="$state/$(basename "$disk").vars.fd"
[[ -f $vars ]] || cp /usr/share/edk2/x64/OVMF_VARS.4m.fd "$vars"
rm -f "$state/qmp.sock"

display=(-display gtk)
[[ $mode == --headless ]] && display=(-display none)

boot=()
[[ $iso != --disk-only ]] && boot=(-cdrom "$iso")

exec qemu-system-x86_64 -machine q35 -enable-kvm -cpu host -m 6G -smp 4 \
    -drive if=pflash,format=raw,readonly=on,file=/usr/share/edk2/x64/OVMF_CODE.4m.fd \
    -drive if=pflash,format=raw,file="$vars" \
    -drive file="$disk",format=raw,if=none,id=d0 -device nvme,drive=d0,serial=rocket0 \
    "${boot[@]}" \
    -vga virtio -device qemu-xhci -device usb-tablet -device usb-kbd \
    -nic user,model=virtio-net-pci \
    -serial file:"$state/serial.log" \
    -qmp unix:"$state/qmp.sock",server=on,wait=off \
    "${display[@]}"
