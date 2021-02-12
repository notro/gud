Raspberry Pi as a Generic USB Display
-------------------------------------


Build:

```
$ git clone https://github.com/notro/gud

$ mkdir tmp && cd tmp

$ ../gud/buildroot/build.sh pi0

$ ls build-raspberrypi0/images/*.img
build-raspberrypi0/images/sdcard.img

```

Release build:

```
$ GUD_VERSION=0.05 ../gud/buildroot/build.sh pi0 release 2>&1 | tee build0.log

$ ls *.{img,zip}
gud-raspberrypi0-0.04.img
gud-raspberrypi0-0.04.zip

```

```GUD_VERSION``` sets the *Device release number* (bcdDevice) on the device descriptor.

```
$ lsusb -v -d 1d50:614d

Bus 003 Device 010: ID 1d50:614d OpenMoko, Inc.
Device Descriptor:
[...]
  idVendor           0x1d50 OpenMoko, Inc.
  idProduct          0x614d
  bcdDevice            0.04
```

```
# cat /etc/os-release
NAME=Buildroot
VERSION=2020.11.1
ID=buildroot
VERSION_ID=2020.11.1
PRETTY_NAME="Buildroot 2020.11.1"
GUD_VERSION=0.04
GUD_VERSION_BCD=0x0004
```

Wiki: https://github.com/notro/gud/wiki/rpi-image
