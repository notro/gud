GUD test suite
==============

A collection of tests that can be used to verify that a GUD device behaves as intended.
The tests disable the host driver and exercises the protocol directly through libusb.

Dependencies
------------

- python3
- numpy
- pytest
- pytest-repeat (optional)

Note: These need to be available for the root user since the tests need to be run as root.


Run protocol tests
------------------

```

# Run all protocol tests
$ sudo pytest tests/

# Run the request test and exit on first failure
$ sudo pytest tests/test_req.py -x

# Skip the stall tests that frequently locks up the Pi
$ sudo pytest tests/ -x -m 'not stall'

# Stress test (requires pytest-repeat)
$ sudo pytest tests/test_req.py --count 100 --repeat-scope session -x -m 'not stall'

```

Other tests
-----------

Get help with ```-h```

```
# Performance tests using various compression ratios
$ sudo python3 tests/perf.py

# Use default mode, RGB565 format, skip compressions and keep display enabled.
$ sudo python3 tests/perf.py -p -f RGB565 -n -k

# Test modes, formats, properties
$ sudo python3 tests/visual.py

# Test only the border test on the default display mode with format RGB565
$ sudo python3 tests/visual.py -p -f RGB565 border

```


USB Compliance Tests
--------------------

The USB Implementers Forum provides tools to verify that a given device adheres to the USB standard.

The USB Command Verifier is only available on Windows machines with a xHCI controller:
- USB20CV for USB 2.0
- USB3CV for USB 3.2
- I didn't find one for USB 1.1

The Chapter 9 Tests should pass for a GUD device.

Links:
- [USB-IF Tools](https://www.usb.org/documents?search=&category%5B0%5D=50)
- [USB 3.0 device compliance test notes](http://billauer.co.il/blog/2019/06/usb-if-compliance-test/)
- https://www.keil.com/pack/doc/CMSIS_DV/group__usbd__comp__test.html


Linux usbtest
-------------

The Linux kernel has a [usbtest](https://elixir.bootlin.com/linux/latest/source/drivers/usb/misc/usbtest.c) module which has some Chapter 9 tests and some other control tests. The tests are run using the [testusb](https://elixir.bootlin.com/linux/latest/source/tools/usb/testusb.c) tool.

```
# Make sure gud doesn't attach
$ sudo modprobe -r gud

$ sudo modprobe usbtest vendor=0x1d50 product=0x614d

# plug in device

$ dmesg
[424132.794826] usb 1-1.4: new full-speed USB device number 29 using xhci_hcd
[424133.404733] usb 1-1.4: new high-speed USB device number 30 using xhci_hcd
[424133.540640] usbtest 1-1.4:1.0: matched module params, vend=0x1d50 prod=0x614d
[424133.540692] usbtest 1-1.4:1.0: Generic USB device
[424133.540718] usbtest 1-1.4:1.0: high-speed {control} tests

# find sysfs path
$ lsusb -t
/:  Bus 02.Port 1: Dev 1, Class=root_hub, Driver=xhci_hcd/4p, 5000M
/:  Bus 01.Port 1: Dev 1, Class=root_hub, Driver=xhci_hcd/1p, 480M
    |__ Port 1: Dev 2, If 0, Class=Hub, Driver=hub/4p, 480M
        |__ Port 2: Dev 4, If 0, Class=Human Interface Device, Driver=usbhid, 1.5M
        |__ Port 2: Dev 4, If 1, Class=Human Interface Device, Driver=usbhid, 1.5M
        |__ Port 4: Dev 30, If 0, Class=Vendor Specific Class, Driver=usbtest, 480M

# /dev/bus/usb/BUS/DEV
$ export DEVICE=/dev/bus/usb/001/030

$ sudo -E ~/testusb -t 9 -c 1
/home/pi/testusb: /dev/bus/usb/001/030 may see only control tests
/dev/bus/usb/001/030 test 9,    0.000865 secs

$ sudo -E ~/testusb -t 10 -c 1 -g 15
/home/pi/testusb: /dev/bus/usb/001/030 may see only control tests
/dev/bus/usb/001/030 test 10,    0.003431 secs

$ dmesg
[424153.667506] usbtest 1-1.4:1.0: TEST 9:  ch9 (subset) control tests, 1 times
[424194.610864] usbtest 1-1.4:1.0: TEST 10:  queue 15 control calls, 1 times

```
