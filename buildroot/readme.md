Raspberry Pi as a GUD USB Display
---------------------------------

Two images that support both Pi Zero and Pi 4:

- pi-lite: Small image with rootfs built into a stripped down kernel. Only serial debug console.

- pi: Supports USB/IP, rootfs can be written to, more debugging options.


Build for one board:

```
$ git clone https://github.com/notro/gud

$ mkdir tmp; cd tmp

# Build only for Pi Zero
$ ../gud/buildroot/build.sh pi linux gud_bcmrpi_defconfig

# Finish image
$ ../gud/buildroot/build.sh pi

$ ls build-raspberrypi/images/sdcard.img
build-raspberrypi/images/sdcard.img

```

Release build:

```
$ GUD_VERSION=0.10 ../gud/buildroot/build.sh pi-lite release 2>&1 | tee build-lite.log

$ ls *.{img,zip}
gud-raspberrypi-lite-0.10.img
gud-raspberrypi-lite-0.10.zip

```

```GUD_VERSION``` sets the *Device release number* (bcdDevice) on the device descriptor.

Host:
```
$ lsusb -v -d 1d50:614d

Bus 003 Device 010: ID 1d50:614d OpenMoko, Inc.
Device Descriptor:
[...]
  idVendor           0x1d50 OpenMoko, Inc.
  idProduct          0x614d
  bcdDevice            0.07
```

Device:
```
# cat /etc/os-release
NAME=Buildroot
VERSION=2021.02.1
ID=buildroot
VERSION_ID=2021.02.1
PRETTY_NAME="Buildroot 2021.02.1"
GUD_VERSION=0.10
GUD_VERSION_BCD=0x0010
```

Wiki: https://github.com/notro/gud/wiki/rpi-image
