#!/bin/bash
# Boots a Rocket OS ISO in QEMU (UEFI) and checks the spec §12 criteria:
# the live desktop session for user 'rocket' starts within the time limit,
# and no systemd unit fails. Usage: qemu-boot.sh <iso>
set -euo pipefail

iso=${1:?usage: qemu-boot.sh <iso>}
[[ -f $iso ]] || { echo "FAIL: no such ISO: $iso" >&2; exit 1; }

ovmf_code=/usr/share/edk2/x64/OVMF_CODE.4m.fd
ovmf_vars_tpl=/usr/share/edk2/x64/OVMF_VARS.4m.fd
tmp=$(mktemp -d)
log=$tmp/serial.log
cp "$ovmf_vars_tpl" "$tmp/vars.fd"

accel=() timeout=900
if [[ -w /dev/kvm ]]; then
    accel=(-enable-kvm -cpu host)
    timeout=120
fi

qemu-system-x86_64 -machine q35 -m 4G -smp 4 "${accel[@]}" \
    -drive if=pflash,format=raw,readonly=on,file="$ovmf_code" \
    -drive if=pflash,format=raw,file="$tmp/vars.fd" \
    -cdrom "$iso" -boot d -vga std -display none \
    -serial file:"$log" -no-reboot &
qemu=$!
trap 'kill $qemu 2>/dev/null || true; wait $qemu 2>/dev/null || true; mkdir -p /var/tmp/rocket-vm; cp "$log" /var/tmp/rocket-vm/boot-serial.log' EXIT

fail() {
    echo "FAIL: $*" >&2
    sed 's/\x1b\[[0-9;]*m//g' "$log" | tail -n 30 >&2
    exit 1
}

start=$SECONDS
while (( SECONDS - start < timeout )); do
    if grep -qE "\[.*FAILED.*\]|Kernel panic|emergency mode" "$log" 2>/dev/null; then
        fail "boot error: $(sed 's/\x1b\[[0-9;]*m//g' "$log" | grep -m1 -E 'FAILED|Kernel panic|emergency mode')"
    fi
    if grep -qE "Started .*Session [0-9]+ of User .*rocket" "$log" 2>/dev/null; then
        echo "PASS: live desktop session for 'rocket' started in $((SECONDS - start))s"
        exit 0
    fi
    kill -0 $qemu 2>/dev/null || fail "QEMU exited early"
    sleep 1
done
fail "timed out after ${timeout}s"
