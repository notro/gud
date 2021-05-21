#!/bin/sh

set -u
set -e

BOARD_DIR="$(dirname $0)"

install -m 0644 -D $BOARD_DIR/extlinux.conf $BINARIES_DIR/extlinux/extlinux.conf

cat << __EOF__ >> "${TARGET_DIR}/etc/fstab"
configfs	/sys/kernel/config	configfs	defaults	0	0
debugfs		/sys/kernel/debug	debugfs	defaults	0	0
__EOF__

if [ -n "${GUD_VERSION:-}" ]; then
    major=$(echo "${GUD_VERSION}" | cut -d. -f1)
    minor=$(echo "${GUD_VERSION}" | cut -d. -f2)
    [ ${#minor} -eq 1 ] && minor=$((${minor}*10))
    GUD_VERSION_BCD=$(printf "0x%02d%02d" ${major} ${minor})

    cat << __EOF__ >> "${TARGET_DIR}/usr/lib/os-release"
GUD_VERSION=${GUD_VERSION}
GUD_VERSION_BCD=${GUD_VERSION_BCD}
__EOF__
fi
