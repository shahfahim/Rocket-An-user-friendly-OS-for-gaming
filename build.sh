#!/bin/bash
# Builds the Rocket OS ISO. Runs inside the rocket-build WSL distro as root.
# Usage: build.sh [--preflight-only] [--clean]
set -euo pipefail

REPO=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
ROCKET_WORK=/var/tmp/rocket-work
MIN_FREE_GB=20

# shellcheck source=scripts/lib/preflight.sh
source "$REPO/scripts/lib/preflight.sh"

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
    rm -rf "${ROCKET_WORK:?}"/*
fi
