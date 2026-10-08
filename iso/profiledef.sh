#!/usr/bin/env bash
# shellcheck disable=SC2034

iso_name="RocketOS"
iso_label="ROCKET_$(date --date="@${SOURCE_DATE_EPOCH:-$(date +%s)}" +%Y%m)"
iso_publisher="Rocket OS <https://github.com/shahfahim/Rocket-An-user-friendly-OS-for-gaming>"
iso_application="Rocket OS Live/Install"
iso_version="$(date --date="@${SOURCE_DATE_EPOCH:-$(date +%s)}" +%Y.%m.%d)"
install_dir="arch"
bootmodes=('uefi.systemd-boot')
pacman_conf="pacman.conf"
airootfs_image_type="squashfs"
airootfs_image_tool_options=('-comp' 'zstd' '-Xcompression-level' '15' '-b' '1M')
file_permissions=(
  ["/etc/shadow"]="0:0:400"
  ["/etc/sudoers.d/rocket-live"]="0:0:440"
  ["/usr/local/bin/rocket-live-user"]="0:0:755"
)
