#!/bin/bash

set -e

BUILDROOT_VERSION="2020.11.1"

if [[ -z ${BR2_DL_DIR} ]]; then
	DL_DIR="$(pwd)/downloads"
	mkdir -p ${DL_DIR}
else
	DL_DIR=${BR2_DL_DIR}
fi

[[ -n ${SSH_KEY_DIR} ]] && KEY_DIR="${SSH_KEY_DIR}" || KEY_DIR="$(pwd)/keys"

SCRIPT_DIR="$(dirname "$(readlink -f "$0")")"

BUILDROOT_SRC_DIR="$(pwd)/buildroot-${BUILDROOT_VERSION}"
BUILDROOT_SRC_FILE_NAME="buildroot-${BUILDROOT_VERSION}.tar.bz2"
BUILDROOT_SRC_FILE="${DL_DIR}/${BUILDROOT_SRC_FILE_NAME}"

info()
{
	msg=$1
	echo "$(tput smso 2>/dev/null)>> ${msg}$(tput rmso 2>/dev/null)"
}

buildroot_source()
{
	if [[ ! -e ${BUILDROOT_SRC_DIR} ]]; then
		if [[ ! -e ${BUILDROOT_SRC_FILE} ]]; then
			info "downloading ${BUILDROOT_SRC_FILE_NAME}"
			wget -O ${BUILDROOT_SRC_FILE} https://buildroot.org/downloads/${BUILDROOT_SRC_FILE_NAME}
		fi

		info "unpacking ${BUILDROOT_SRC_FILE}"
		tar xf ${BUILDROOT_SRC_FILE}
	fi
}

ssh_keys()
{
	if [[ ! -f ${KEY_DIR}/ssh_host_rsa_key ]]; then
		info "creating ssh keys in ${KEY_DIR}"
		mkdir -p "${KEY_DIR}"
		ssh-keygen -q -t rsa -f "${KEY_DIR}/ssh_host_rsa_key" -N ""
		ssh-keygen -q -t dsa -f "${KEY_DIR}/ssh_host_dsa_key" -N ""
		ssh-keygen -q -t ecdsa -f "${KEY_DIR}/ssh_host_ecdsa_key" -N ""
	fi
}

configure()
{
	d="build-$1"
	f="${d}/.config"

	if [[ -n $2 ]]; then
		rm -f ${f}
	fi

	if [[ -e ${f} ]]; then
		return
	fi

	info "Configure"
	mkdir -p ${d}
	(cd ${d} && make O=../${d} -C ${BUILDROOT_SRC_DIR} BR2_EXTERNAL=${SCRIPT_DIR}/external/ BR2_DL_DIR=${DL_DIR} $1_defconfig)
}

make_target()
{
	info "make $2"
	(cd "build-$1" && SSH_KEY_DIR=${KEY_DIR} make $2)
}

release()
{
	img="build-$1/images/sdcard.img"

	if [ ! -e ${img} ]; then
		echo "File missing: ${img}"
		exit 1
	fi

	if ! grep -q GUD_VERSION "build-$1/target/usr/lib/os-release"; then
		echo "Not built with GUD_VERSION set"
		exit 1
	fi

	fn="gud-$1-${GUD_VERSION}"

	cp -v ${img} "${fn}.img"
	echo "${fn}.zip:"
	rm -f "${fn}.zip"
	zip "${fn}.zip" "${fn}.img"
}

usage()
{
	echo "usage: build.sh [board] [build target]"
}


if [[ $# -eq 1 ]]; then
	case $1 in
		distclean )
			info "distclean"
			rm -rf ${BUILDROOT_SRC_DIR}
			rm -rf build-*
			rm -f *.img *.zip
			[[ -z ${SSH_KEY_DIR} ]] && rm -rf "${KEY_DIR}"
			if [[ "${DL_DIR}" != "${BR2_DL_DIR}" ]]; then
				rm -rf ${DL_DIR}
			fi
			exit 0
			;;
		clean )
			info "clean"
			rm -rf build-*
			rm -f *.img
			exit 0
			;;
	esac
	target=""
elif [[ $# -eq 2 ]]; then
	target=$2
else
	usage
	exit 1
fi

case $1 in
	pi0 )
		board=raspberrypi0
		;;
	pi4 )
		board=raspberrypi4
		;;
	* )
		echo "Supported boards are: pi0 pi4"
		exit 1
esac

buildroot_source
ssh_keys

case $target in
	configure )
		configure ${board} force
		;;
	release )
		if [ -z "${GUD_VERSION}" ]; then
			echo "GUD_VERSION is not set"
			exit 1
		fi
		if [ ! -e "build-${board}/images/sdcard.img" ]; then
			configure ${board}
			make_target ${board}
		fi
		release ${board}
		;;
	* )
		configure ${board}
		make_target ${board} ${target}
		;;
esac
