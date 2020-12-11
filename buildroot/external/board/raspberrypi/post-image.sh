#!/bin/bash

set -e

BOARD_DIR="$(dirname $0)"
BOARD_NAME="$(basename ${BOARD_DIR})"
GENIMAGE_CFG="${BOARD_DIR}/genimage-${BOARD_NAME}.cfg"
GENIMAGE_TMP="${BUILD_DIR}/genimage.tmp"

cat << __EOF__ > "${BINARIES_DIR}/rpi-firmware/config.txt"
#uart_2ndstage=1
#dtdebug=1
disable_splash=1

disable_overscan=1

# prevent the firmware from adding video= display modes through the kernel command line
disable_fw_kms_setup=1

[pi0]
dtoverlay=dwc2,dr_mode=otg
dtoverlay=vc4-kms-v3d,noaudio,nocomposite

[pi0w]
dtoverlay=disable-bt

[pi4]
dtoverlay=disable-bt
dtoverlay=dwc2,dr_mode=peripheral
dtoverlay=vc4-kms-v3d-pi4,noaudio

__EOF__

# TODO this can be moved out to a file now
CMDLINE="root=/dev/mmcblk0p2 rootwait console=ttyAMA0,115200 console=tty1"
CMDLINE+=" gud_gadget.force_rg16=1 video=simplefb:off vt.global_cursor_default=0 quiet"
echo "${CMDLINE}" > "${BINARIES_DIR}/rpi-firmware/cmdline.txt"

cp "${BUILD_DIR}/linux-custom/arch/arm/boot/dts/bcm2708-rpi-zero-w.dtb" "${BINARIES_DIR}" 2>/dev/null

DTB_OVERLAYS="${BINARIES_DIR}/overlays"
mkdir -p "${DTB_OVERLAYS}"
cp ${BUILD_DIR}/linux-custom/arch/arm/boot/dts/overlays/*.dtbo "${DTB_OVERLAYS}"

cp "${BOARD_DIR}/interfaces.${BOARD_NAME}" "${BINARIES_DIR}/interfaces.disabled"
cp "${BOARD_DIR}/wpa_supplicant.conf" "${BINARIES_DIR}"

trap 'rm -rf "${ROOTPATH_TMP}"' EXIT
ROOTPATH_TMP="$(mktemp -d)"

rm -rf "${GENIMAGE_TMP}"

genimage \
	--rootpath "${ROOTPATH_TMP}"   \
	--tmppath "${GENIMAGE_TMP}"    \
	--inputpath "${BINARIES_DIR}"  \
	--outputpath "${BINARIES_DIR}" \
	--config "${GENIMAGE_CFG}"

exit $?
