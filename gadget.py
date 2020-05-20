# SPDX-License-Identifier: CC0-1.0

from collections import OrderedDict
import glob
import os
from pathlib import Path
import subprocess
import time

class GadgetFunction:
    def __init__(self, instance, mountpoint, args):
        self.instance = instance
        self.mountpoint = mountpoint
        self.args = args
        self.process = None

    def start(self):
        print('mount:', self.instance, self.mountpoint)
        try:
            os.mkdir(self.mountpoint)
        except FileExistsError:
            pass
        subprocess.call(['mount', '-t', 'functionfs', self.instance, self.mountpoint])
        subprocess.call(['ls', '-l', self.mountpoint])

        print('Popen:', self.args)
        self.process = subprocess.Popen(self.args)
        time.sleep(1)
        if self.process.returncode is not None:
            raise OSError('Failed to start {!r}, returncode={}'.format(self.process.instance, self.process.returncode))

    def stop(self):
        if self.process and self.process.returncode is None:
            print('terminate:', self.instance)

            self.process.terminate()
            try:
                self.process.wait(3)
            except TimeoutExpired:
                self.process.kill()
                try:
                    self.process.wait(3)
                except TimeoutExpired:
                    print('ERROR: Failed to stop', self.instance)

        if os.path.ismount(self.mountpoint):
            print('umount:', self.mountpoint)
            subprocess.call(['umount', self.mountpoint])
        try:
            os.rmdir(self.mountpoint)
        except FileNotFoundError:
            pass

class Gadget:
    SYSFS_PATH = '/sys'
    CONFIGFS_GADGET_HOME = '/sys/kernel/config/usb_gadget'

    def __init__(self, name, config, udc=None):
        self.name = name
        self.root = Path(Gadget.CONFIGFS_GADGET_HOME) / Path(name)
        self.config = config
        self.udc = udc
        self.functions = []

    def write_udc(self, val):
        print('UDC:', repr(val))
        with self.root.joinpath('UDC').open('w') as f:
            f.write(val)

    def enable(self):
        udc = self.udc
        if not udc:
            for item in Path(Gadget.SYSFS_PATH).joinpath('class/udc/').iterdir():
                udc = item.name
                break
        if not udc:
            raise RuntimeError('No USB controller')
        self.write_udc(udc)

    def disable(self):
        self.write_udc('')

    def process(self, rootpath, d):
        for key, value in d.items():
            if value is None:
                continue
            path = rootpath / Path(key)
            #print('path.parts[-2]:', path.parts[-2], '::', path.parts[-2] in ['configs', 'functions', 'strings'])
            #print('path.parts', path.parts)
            if isinstance(value, dict):
                if path.parts[-2] in ['configs', 'functions', 'strings'] or ('functions' in path.parts and path.parts.index('functions') < (len(path.parts) - 1)):
                    print(path)
                    path.mkdir()
                self.process(path, value)
            elif path.exists():
                print(path, ':=', value)
                if isinstance(value, int):
                    value = str(value)
                if isinstance(value, str):
                    value = value.encode('ascii')
                with path.open('wb') as f:
                    f.write(value)
            elif path.parts[-3] == 'configs':
                # Non-existent entry in config is a function link
                print('link:', path)
                dst = rootpath.parent.parent.joinpath('functions', key)
                path.symlink_to(dst)
                #print('     ', dst)
            elif path.parts[-3] == 'functions' and key == 'handler':
                instance = path.parts[-2].split('.')[-1]
                print('function handler:', instance)
                print('    mount:', value[0])
                self.functions.append(GadgetFunction(instance, value[0], value[1]))
            else:
                print('WARNING: Unknown entry:', path, value)

    def __enter__(self):
        self.root.mkdir(exist_ok=True)
        config = OrderedDict(self.config)
        # Defer symlinking to last so the target is present, broken symlinks are not allowed.
        configs = config.pop('configs', None)
        if configs:
            config['configs'] = configs
        try:
            self.process(self.root, config)
            for function in self.functions:
                function.start()
        except OSError as e:
            print(self)
            self.__exit__(e)
            raise
        return self

    @staticmethod
    def rmdir(path):
        for item in path.iterdir():
            if item.is_dir() and not item.is_symlink():
                Gadget.rmdir(item)
            else:
                try:
                    item.unlink()
                except PermissionError:
                    pass
        try:
            path.rmdir()
        except PermissionError:
            pass

    def __exit__(self, *args):
        if self.root.exists():
            self.disable()
            for function in self.functions:
                try:
                    function.stop()
                except OSError as e:
                    print('Failed to stop', function.instance, e)
            self.rmdir(self.root)

    @staticmethod
    def strdir(indent, path):
        s = ' ' * indent + path.name + '/\n'
        indent += len(path.name)
        for item in path.iterdir():
            if item.is_dir():
                s += Gadget.strdir(indent, item)
            else:
                with item.open('rb') as f:
                    v = f.read()
                try:
                    v = str(v, 'ascii')
                except UnicodeDecodeError:
                    pass
                s += ' ' * indent + item.name + ': ' + repr(v.strip()) + '\n'
        return s

    def __str__(self):
        return Gadget.strdir(0, self.root)


# sudo ./hid_gadget_test /dev/hidg0 keyboard
hid_keyboard = {
    'protocol': '1',
    'subclass': '1',
    'report_length': '8',
#    'report_desc': '\x05\x01\x09\x06\xa1\x01\x05\x07\x19\xe0\x29\xe7\x15\x00\x25\x01\x75\x01\x95\x08\x81\x02\x95\x01\x75\x08\x81\x03\x95\x05\x75\x01\x05\x08\x19\x01\x29\x05\x91\x02\x95\x01\x75\x03\x91\x03\x95\x06\x75\x08\x15\x00\x25\x65\x05\x07\x19\x00\x29\x65\x81\x00\xc0',

    'report_desc': bytes([0x05, 0x01, 0x09, 0x06, 0xa1, 0x01, 0x05, 0x07, 0x19, 0xe0, 0x29, 0xe7, 0x15, 0x00, 0x25, 0x01, 0x75, 0x01, 0x95, 0x08, 0x81, 0x02, 0x95, 0x01, 0x75, 0x08, 0x81, 0x03, 0x95, 0x05, 0x75, 0x01, 0x05, 0x08, 0x19, 0x01, 0x29, 0x05, 0x91, 0x02, 0x95, 0x01, 0x75, 0x03, 0x91, 0x03, 0x95, 0x06, 0x75, 0x08, 0x15, 0x00, 0x25, 0x65, 0x05, 0x07, 0x19, 0x00, 0x29, 0x65, 0x81, 0x00, 0xc0]),

}


# https://www.codeproject.com/Articles/1001891/A-USB-HID-Keyboard-Mouse-Touchscreen-emulator-with
# https://github.com/NicoHood/HID/issues/123
# https://gist.github.com/mbt28/406bdf15a248029c774085832c7c0c0c

# $ gcc -o hid_gadget_test ~/work/tinydrm.misc/sud/test/hid_gadget_test.c
# $ sudo ./hid_gadget_test /dev/hidg0 touch
hid_touch = {
    'protocol': '1',
    'subclass': '1',
    'report_length': '7',
    'report_desc': bytes([

        0x05, 0x0D,        # Usage Page (Digitizer)
        0x09, 0x04,        # Usage (Touch Screen)
        0xA1, 0x01,        # Collection (Application)
        0x09, 0x55,        #   Usage (Contact Count Maximum)
        0x25, 0x01,        #   Logical Maximum (1)
        0xB1, 0x02,        #   Feature (Data,Var,Abs,No Wrap,Linear,Preferred State,No Null Position,Non-volatile)
        0x09, 0x54,        #   Usage (Contact Count)
        0x95, 0x01,        #   Report Count (1)
        0x75, 0x08,        #   Report Size (8)
        0x81, 0x02,        #   Input (Data,Var,Abs,No Wrap,Linear,Preferred State,No Null Position)
        0x09, 0x22,        #   Usage (Finger)
        0xA1, 0x02,        #   Collection (Logical)
        0x09, 0x51,        #     Usage (Contact Identifier)
        0x75, 0x08,        #     Report Size (8)
        0x95, 0x01,        #     Report Count (1)
        0x81, 0x02,        #     Input (Data,Var,Abs,No Wrap,Linear,Preferred State,No Null Position)
        0x09, 0x42,        #     Usage (Tip Switch)
        0x09, 0x32,        #     Usage (In Range)
        0x15, 0x00,        #     Logical Minimum (0)
        0x25, 0x01,        #     Logical Maximum (1)
        0x75, 0x01,        #     Report Size (1)
        0x95, 0x02,        #     Report Count (2)
        0x81, 0x02,        #     Input (Data,Var,Abs,No Wrap,Linear,Preferred State,No Null Position)
        0x95, 0x06,        #     Report Count (6)
        0x81, 0x03,        #     Input (Const,Var,Abs,No Wrap,Linear,Preferred State,No Null Position)
        0x05, 0x01,        #     Usage Page (Generic Desktop Ctrls)
        0x09, 0x30,        #     Usage (X)
        0x09, 0x31,        #     Usage (Y)
        0x16, 0x00, 0x00,  #     Logical Minimum (0)
        0x26, 0x10, 0x27,  #     Logical Maximum (10000)
        0x36, 0x00, 0x00,  #     Physical Minimum (0)
        0x46, 0x10, 0x27,  #     Physical Maximum (10000)
        0x66, 0x00, 0x00,  #     Unit (None)
        0x75, 0x10,        #     Report Size (16)
        0x95, 0x02,        #     Report Count (2)
        0x81, 0x02,        #     Input (Data,Var,Abs,No Wrap,Linear,Preferred State,No Null Position)
        0xC0,              #   End Collection
        0xC0,              # End Collection
    ])
}


def drm_dev():
    dirs = glob.glob('/sys/class/drm/card[0-63]/card[0-63]-*/')
    p = Path(dirs[0])
    return int(p.parent.name[4:])


def backlight_dev():
    dirs = glob.glob('/sys/class/backlight/*/')
    if not dirs:
        return ''
    p = Path(dirs[0])
    return p.name


config = {
    'bcdDevice': None,
    'bcdUSB': None,
    'bDeviceClass': None,
    'bDeviceProtocol': None,
    'bDeviceSubClass': None,
    'bMaxPacketSize0': None,
    'idVendor': '0x1d50',
    'idProduct': '0x614d',

    'configs': {
        'c.1': {
            'bmAttributes': None,
            'gud_drm.0': 'link',
            #'hid.usb0': 'link',
            'MaxPower': None,
            'strings': {

            },
        },
    },

    'functions': {
        'gud_drm.0': {
            'drm_dev': drm_dev(),
            'backlight_dev': backlight_dev(),
        },

        #'hid.usb0': hid_keyboard,
        #'hid.usb0': hid_touch,
    },

    'os_desc': {
        'b_vendor_code' : None,
        'qw_sign' : None,
        'use' : None,
    },

    'strings': {
        '0x409': {
            'manufacturer': None,
            'product': 'PiZero Display Gadget',
            'serialnumber': None,
        },
    },
}


def main():
    import signal
    terminate = False
    def sigint_handler(signalnum, frame):
        nonlocal terminate
        terminate = True
    signal.signal(signal.SIGINT, sigint_handler)
    signal.signal(signal.SIGTERM, sigint_handler)

    udc = None
    #udc = 'usbip-vudc.0'

    with Gadget('Display', config, udc) as gadget:
        print('HELLO')
        print(gadget)
        print('-------------------------')
        time.sleep(1)
        gadget.enable()
        while not terminate:
            try:
                time.sleep(0.1)
            except KeyboardInterrupt:
                print('Ctrl-C', flush=True)
            except Exception as e:
                print('EXCEPTION: ', e, flush=True)
        gadget.disable()


if __name__ == '__main__':
    main()
