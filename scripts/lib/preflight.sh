# Preflight checks for build.sh. Source this file; each function returns
# non-zero and prints "ERROR: <reason>. Fix: <hint>" on failure.

check_root() {
    if [[ $(id -u) -ne 0 ]]; then
        echo "ERROR: must run as root. Fix: run via build.ps1 or 'wsl -u root'." >&2
        return 1
    fi
}

check_loop_devices() {
    if ! losetup -f &>/dev/null; then
        echo "ERROR: no loop devices available. Fix: run 'modprobe loop' or use a Hyper-V Arch VM as build host." >&2
        return 1
    fi
}

# check_disk_space <dir> <min_gb>
check_disk_space() {
    local dir=$1 min_gb=$2 avail
    avail=$(df --output=avail -BG "$dir" | tail -n1 | tr -dc '0-9')
    if [[ -z $avail || $avail -lt $min_gb ]]; then
        echo "ERROR: only ${avail:-0} GB free in $dir, need $min_gb GB. Fix: free up space in the WSL disk." >&2
        return 1
    fi
}
