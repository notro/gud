#!/bin/bash

set -e

BOARD_DIR="$(dirname $0)"
GENIMAGE_CFG="${BOARD_DIR}/genimage.cfg"
GENIMAGE_TMP="${BUILD_DIR}/genimage.tmp"

BOOTFS="${BINARIES_DIR}/bootfs"
mkdir -p "${BOOTFS}"

RPI_FIRMWARE_BOOT="${BUILD_DIR}"/rpi-firmware-*/boot

cp ${RPI_FIRMWARE_BOOT}/bootcode.bin "${BOOTFS}"
cp ${RPI_FIRMWARE_BOOT}/start.elf "${BOOTFS}"
cp ${RPI_FIRMWARE_BOOT}/fixup.dat "${BOOTFS}"

cp ${RPI_FIRMWARE_BOOT}/start4.elf "${BOOTFS}"
cp ${RPI_FIRMWARE_BOOT}/fixup4.dat "${BOOTFS}"


cp "${BOARD_DIR}/config.txt" "${BOOTFS}"
cp "${BOARD_DIR}/cmdline.txt" "${BOOTFS}"


DTBS="${BUILD_DIR}/linux-custom/arch/arm/boot/dts"

if [[ -f "${BINARIES_DIR}/kernel.img" ]]; then
	cp "${BINARIES_DIR}/kernel.img" "${BOOTFS}"
	cp "${DTBS}/bcm2708-rpi-zero.dtb" "${BOOTFS}"
	cp "${DTBS}/bcm2708-rpi-zero-w.dtb" "${BOOTFS}"
fi

if [[ -f "${BINARIES_DIR}/kernel7l.img" ]]; then
	cp "${BINARIES_DIR}/kernel7l.img" "${BOOTFS}"
	cp "${DTBS}/bcm2711-rpi-4-b.dtb" "${BOOTFS}"
fi

DTB_OVERLAYS="${BOOTFS}/overlays"
mkdir -p "${DTB_OVERLAYS}"
cp ${BUILD_DIR}/linux-custom/arch/arm/boot/dts/overlays/*.dtbo "${DTB_OVERLAYS}"

rm -rf "${GENIMAGE_TMP}"

genimage \
	--rootpath "${BOOTFS}"   \
	--tmppath "${GENIMAGE_TMP}"    \
	--inputpath "${BINARIES_DIR}"  \
	--outputpath "${BINARIES_DIR}" \
	--config "${GENIMAGE_CFG}"

exit $?
