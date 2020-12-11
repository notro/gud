#!/bin/sh

set -u
set -e

if [ -e ${TARGET_DIR}/etc/inittab ]; then
    grep -qE '^tty1::' ${TARGET_DIR}/etc/inittab || \
	sed -i '/GENERIC_SERIAL/a\
tty1::respawn:/usr/bin/getty_fbcon # HDMI console\
ttyGS0::respawn:/sbin/getty -L ttyGS0 115200 vt100' ${TARGET_DIR}/etc/inittab
fi

cat << __EOF__ >> "${TARGET_DIR}/etc/fstab"
configfs	/sys/kernel/config	configfs	defaults	0	0
debugfs		/sys/kernel/debug	debugfs	defaults	0	0
/dev/mmcblk0p1	/boot		vfat	defaults,ro	0	2
__EOF__

if [ -n "${GUD_VERSION}" ]; then
    major=$(echo "${GUD_VERSION}" | cut -d. -f1)
    minor=$(echo "${GUD_VERSION}" | cut -d. -f2)
    [ ${#minor} -eq 1 ] && minor=$((${minor}*10))
    GUD_VERSION_BCD=$(printf "0x%02d%02d" ${major} ${minor})

    cat << __EOF__ >> "${TARGET_DIR}/usr/lib/os-release"
GUD_VERSION=${GUD_VERSION}
GUD_VERSION_BCD=${GUD_VERSION_BCD}
__EOF__
fi

install -D -m 0600 ${SSH_KEY_DIR}/ssh_host_*_key ${TARGET_DIR}/etc/ssh

rm -f "${TARGET_DIR}/etc/init.d/S02sysctl"
rm -f "${TARGET_DIR}/etc/init.d/S20urandom"
rm -f "${TARGET_DIR}/etc/avahi/services/sftp-ssh.service"
