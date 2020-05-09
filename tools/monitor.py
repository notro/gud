# SPDX-License-Identifier: CC0-1.0

import argparse
import copy
import ctypes
import datetime
import errno
import fcntl
import mmap
import os
import sys

# HMM $ sudo apt-get install libusb-1.0-0-dev
# $ sudo pip3 install pyusb
import usb.core

#######################################################################################################################################
#
# usbmon abstraction
#

# include/uapi/asm-generic/ioctl.h

_IOC_NRBITS     = 8
_IOCtype_BITS   = 8
_IOC_SIZEBITS   = 14
_IOC_DIRBITS    = 2

_IOC_NRMASK     = ((1 << _IOC_NRBITS) - 1)
_IOCtype_MASK   = ((1 << _IOCtype_BITS) - 1)
_IOC_SIZEMASK   = ((1 << _IOC_SIZEBITS) - 1)
_IOC_DIRMASK    = ((1 << _IOC_DIRBITS) - 1)

_IOC_NRSHIFT    = 0
_IOCtype_SHIFT  = (_IOC_NRSHIFT + _IOC_NRBITS)
_IOC_SIZESHIFT  = (_IOCtype_SHIFT + _IOCtype_BITS)
_IOC_DIRSHIFT   = (_IOC_SIZESHIFT + _IOC_SIZEBITS)

_IOC_NONE       = 0
_IOC_WRITE      = 1
_IOC_READ       = 2

def _IOC(_dir,type_,nr,size):
    return ((_dir)  << _IOC_DIRSHIFT) | \
           ((type_) << _IOCtype_SHIFT) | \
           ((nr)   << _IOC_NRSHIFT) | \
           ((size) << _IOC_SIZESHIFT)

def _IOCtype_CHECK(t):
    return ctypes.sizeof(t)

def _IO(type_,nr):
    return _IOC(_IOC_NONE,(type_),(nr),0)

def _IOR(type_,nr,size):
    return _IOC(_IOC_READ,(type_),(nr),(_IOCtype_CHECK(size)))

def _IOW(type_,nr,size):
    return _IOC(_IOC_WRITE,(type_),(nr),(_IOCtype_CHECK(size)))

def _IOWR(type_,nr,size):
    return _IOC(_IOC_READ|_IOC_WRITE,(type_),(nr),(_IOCtype_CHECK(size)))


# include/uapi/linux/usb/ch9.h
class usb_ctrlrequest(ctypes.LittleEndianStructure):
    _fields_ = [
        ('bRequestType', ctypes.c_uint8),
        ('bRequest', ctypes.c_uint8),
        ('wValue', ctypes.c_uint16),
        ('wIndex', ctypes.c_uint16),
        ('wLength', ctypes.c_uint16),
    ]
    _pack_ = 1

USB_DIR_IN = 0x80


BUFF_DFL   = 300 * 1024
SETUP_LEN  = 8


# mon_bin_hdr.xfer_type
PIPE_ISOCHRONOUS    = 0
PIPE_INTERRUPT      = 1
PIPE_CONTROL        = 2
PIPE_BULK           = 3


class mon_bin_hdr(ctypes.Structure):
    _fields_ = [
        ('id', ctypes.c_uint64),            # URB ID - from submission to callback
        ('type', ctypes.c_char),            # Same as in text API; extensible.
        ('xfer_type', ctypes.c_ubyte),      # ISO, Intr, Control, Bulk
        ('epnum', ctypes.c_ubyte),          # Endpoint number and transfer direction
        ('devnum', ctypes.c_ubyte),         # Device address
        ('busnum', ctypes.c_ushort),        # Bus number
        ('flag_setup', ctypes.c_char),      # Values: '-', 'Z'
        ('flag_data', ctypes.c_char),       # Values: 0, '<', '>', 'Z', 'D'
        ('ts_sec', ctypes.c_int64),         # ktime_get_real_ts64
        ('ts_usec', ctypes.c_int32),        # ktime_get_real_ts64
        ('status', ctypes.c_int),
        ('len_urb', ctypes.c_uint),         # Length of data (submitted or actual)
        ('len_cap', ctypes.c_uint),         # Delivered length
        # Only care about setup so skip union/iso
        ('setup', ctypes.c_ubyte * SETUP_LEN),    # Only for Control S-type
        ('interval', ctypes.c_int),
        ('start_frame', ctypes.c_int),
        ('xfer_flags', ctypes.c_uint),
        ('ndesc', ctypes.c_uint),            # Actual number of ISO descriptors
    ]

    # Useful for printing in the drop callback
    def __str__(self):
        fields = ["{}: {}".format(field[0], getattr(self, field[0])) for field in self._fields_]
        return "{}: {{{}}}".format(self.__class__.__name__, ", ".join(fields))


class mon_bin_stats(ctypes.Structure):
    _fields_ = [
        ('queued', ctypes.c_uint32),
        ('dropped', ctypes.c_uint32),
    ]


class mon_bin_mfetch(ctypes.Structure):
    _fields_ = [
        #('offvec', ctypes.c_uint32),    # Vector of events fetched
        ('offvec', ctypes.POINTER(ctypes.c_uint32)),    # Vector of events fetched
        ('nfetch', ctypes.c_uint32),    # Number of events to fetch (out: fetched)
        ('nflush', ctypes.c_uint32),    # Number of events to flush
    ]


# ioctl macros
MON_IOC_MAGIC = 0x92

#MON_IOCQ_URB_LEN    = _IO(MON_IOC_MAGIC, 1)
MON_IOCG_STATS      = _IOR(MON_IOC_MAGIC, 3, mon_bin_stats)
MON_IOCT_RING_SIZE  = _IO(MON_IOC_MAGIC, 4)
MON_IOCX_MFETCH     = _IOWR(MON_IOC_MAGIC, 7, mon_bin_mfetch)
#MON_IOCH_MFLUSH     = _IO(MON_IOC_MAGIC, 8)


class USBmonURB:
    def __init__(self, first, second, data):
        # first is a Submit hdr
        self.first = first
        # second is either a Complete or Error hdr
        self.second = second
        self.data = data # len(data) != len_urb if capped by usbmon

        self.id = first.id
        self.type = first.xfer_type
        self.epnum = first.epnum
        self.devnum = first.devnum
        self.busnum = first.busnum
        self.ts_start = first.ts_sec + (first.ts_usec * 1e-6)
        self.ts_end = second.ts_sec + (second.ts_usec * 1e-6)
        self.status = second.status
        self.len = second.len_urb # Actual URB len

        if first.xfer_type == PIPE_CONTROL and first.flag_setup == b'\x00':
            self.setup = usb_ctrlrequest.from_buffer_copy(first.setup)
        else:
            self.setup = None

        self.dirin = True if self.epnum & USB_DIR_IN else False

    def __str__(self):
        type_name = ('Z', 'I', 'C', 'B')[self.type]
        s = f'URB {type_name}:'

        if self.setup:
            s += f' bRequestType={self.setup.bRequestType:02x} bRequest={self.setup.bRequest:02x} wValue={self.setup.wValue:04x}'
            s += f' wIndex={self.setup.wIndex:04x} wLength={self.setup.wLength:04x}'

        s += f' len={len(self.data)}'
        if len(self.data) != self.len:
            s += f'({self.len}'
        if self.len != self.first.len_urb:
            s = f'/{self.first.len_urb}'
        if len(self.data) != self.len:
            s += ')'

        return s


class USBmon:
    def __init__(self, busnum, bufsize=BUFF_DFL, debug=False, drop_cb=None):
        self.busnum = busnum
        self.debug = debug
        self.drop_cb = drop_cb

        self.nflush = 0
        self.hdr = {}
        self.data = {}

        self.file = open(f'/dev/usbmon{busnum}', 'r+b', buffering=0)
        fcntl.ioctl(self.file, MON_IOCT_RING_SIZE, bufsize)
        self.map = mmap.mmap(self.file.fileno(), bufsize)

    def fetch(self):
        vec = ctypes.c_uint32()
        offvec = ctypes.pointer(vec)
        arg = mon_bin_mfetch(offvec, 1, self.nflush)

        fcntl.ioctl(self.file, MON_IOCX_MFETCH, arg)
        self.nflush = arg.nfetch
        if arg.nfetch == 0:
            raise StopIteration
        return vec.value

    def drop(self, hdr, reason):
        arg = mon_bin_stats()
        fcntl.ioctl(self.file, MON_IOCG_STATS, arg)
        if self.drop_cb:
            self.drop_cb(hdr, reason, arg.dropped)

    def __iter__(self):
        return self

    def __next__(self):
        first = None
        data = None

        while True:
            try:
                offset = self.fetch()
            except KeyboardInterrupt:
                raise StopIteration

            # UAPI: sizeof(hdr) == 64
            hdr = mon_bin_hdr.from_buffer_copy(self.map[offset : offset + 64])

            if self.debug:
                print(f'{hdr}')

            if hdr.type == b'@': # Filler packet
                continue

#            if not first and hdr.type != b'S':
#                self.drop(hdr, 'Not a Submit header')
#                continue
#
#            if first and hdr.type == b'S':
#                self.drop(hdr, 'Not a Complete or Error header')
#                first = None
#                data = None
#                continue

            if hdr.flag_data == b'\x00':
                data_offset = offset + 64
                self.data[hdr.id] = self.map[data_offset : data_offset + hdr.len_cap]

            if hdr.type == b'S':
                self.hdr[hdr.id] = hdr
                continue

            submit = self.hdr.pop(hdr.id, None)
            if not submit:
                self.hdr[hdr.id] = hdr
                continue

            if (submit.xfer_type != hdr.xfer_type or
                submit.epnum != hdr.epnum or
                submit.devnum != hdr.devnum or
                submit.busnum != hdr.busnum
                #submit.id != hdr.id
            ):
                self.drop(submit, 'Did not match the next header')
                self.drop(hdr, 'Did not match the previous header')
                #first = None
                #data = None
                continue

            if submit.xfer_type == PIPE_CONTROL and submit.flag_setup != b'\x00':
                self.drop(submit, 'Missing SETUP data')
                self.drop(hdr, 'Missing SETUP data, cont.')
                #first = None
                #data = None
                continue

            data = self.data.pop(hdr.id, None)

            #if len(self.hdr > 50):
            #    self.hdr = { i:hdr for i, hdr in self.hdr.items() if hdr.time > some_time }

            return USBmonURB(submit, hdr, data)

####################################################################################################
#
# include/drm/gud_drm.h
#

USB_DIR_IN               = 0x80
USB_TYPE_VENDOR          = (0x02 << 5)
USB_RECIP_INTERFACE      = 0x01

GUD_DRM_USB_DT_INTERFACE = (USB_TYPE_VENDOR | 0x4)

def BIT(n):
    return 1 << n

GUD_DRM_STATUS_PENDING  = BIT(0)

USB_REQ_GET_DESCRIPTOR = 0x06

GUD_DRM_USB_REQ_SET_VERSION = 0x30
GUD_DRM_USB_REQ_GET_FORMATS = 0x40
GUD_DRM_USB_REQ_GET_PROPERTIES = 0x41
GUD_DRM_USB_REQ_GET_CONNECTOR = 0x50
GUD_DRM_USB_REQ_GET_CONNECTOR_PROPERTIES = 0x51
GUD_DRM_USB_REQ_GET_CONNECTOR_TV_MODE_VALUES = 0x52
GUD_DRM_USB_REQ_SET_CONNECTOR_FORCE_DETECT = 0x53
GUD_DRM_USB_REQ_GET_CONNECTOR_STATUS = 0x54
GUD_DRM_USB_REQ_GET_CONNECTOR_MODES = 0x55
GUD_DRM_USB_REQ_GET_CONNECTOR_EDID = 0x56
GUD_DRM_USB_REQ_SET_BUFFER = 0x60
GUD_DRM_USB_REQ_SET_MODE_CHECK = 0x61
GUD_DRM_USB_REQ_SET_MODE_COMMIT = 0x62
GUD_DRM_USB_REQ_SET_CONTROLLER_ENABLE = 0x63
GUD_DRM_USB_REQ_SET_DISPLAY_ENABLE = 0x64

req_to_name = {
    USB_REQ_GET_DESCRIPTOR: 'USB_REQ_GET_DESCRIPTOR',
    GUD_DRM_USB_REQ_SET_VERSION: 'GUD_DRM_USB_REQ_SET_VERSION',
    GUD_DRM_USB_REQ_GET_FORMATS: 'GUD_DRM_USB_REQ_GET_FORMATS',
    GUD_DRM_USB_REQ_GET_PROPERTIES: 'GUD_DRM_USB_REQ_GET_PROPERTIES',
    GUD_DRM_USB_REQ_GET_CONNECTOR: 'GUD_DRM_USB_REQ_GET_CONNECTOR',
    GUD_DRM_USB_REQ_GET_CONNECTOR_PROPERTIES: 'GUD_DRM_USB_REQ_GET_CONNECTOR_PROPERTIES',
    GUD_DRM_USB_REQ_GET_CONNECTOR_TV_MODE_VALUES: 'GUD_DRM_USB_REQ_GET_CONNECTOR_TV_MODE_VALUES',
    GUD_DRM_USB_REQ_SET_CONNECTOR_FORCE_DETECT: 'GUD_DRM_USB_REQ_SET_CONNECTOR_FORCE_DETECT',
    GUD_DRM_USB_REQ_GET_CONNECTOR_STATUS: 'GUD_DRM_USB_REQ_GET_CONNECTOR_STATUS',
    GUD_DRM_USB_REQ_GET_CONNECTOR_MODES: 'GUD_DRM_USB_REQ_GET_CONNECTOR_MODES',
    GUD_DRM_USB_REQ_GET_CONNECTOR_EDID: 'GUD_DRM_USB_REQ_GET_CONNECTOR_EDID',
    GUD_DRM_USB_REQ_SET_BUFFER: 'GUD_DRM_USB_REQ_SET_BUFFER',
    GUD_DRM_USB_REQ_SET_MODE_CHECK: 'GUD_DRM_USB_REQ_SET_MODE_CHECK',
    GUD_DRM_USB_REQ_SET_MODE_COMMIT: 'GUD_DRM_USB_REQ_SET_MODE_COMMIT',
    GUD_DRM_USB_REQ_SET_CONTROLLER_ENABLE: 'GUD_DRM_USB_REQ_SET_CONTROLLER_ENABLE',
    GUD_DRM_USB_REQ_SET_DISPLAY_ENABLE: 'GUD_DRM_USB_REQ_SET_DISPLAY_ENABLE',
}


GUD_DRM_PROPERTY_TV_SELECT_SUBCONNECTOR     = 1
GUD_DRM_PROPERTY_TV_LEFT_MARGIN             = 2
GUD_DRM_PROPERTY_TV_RIGHT_MARGIN            = 3
GUD_DRM_PROPERTY_TV_TOP_MARGIN              = 4
GUD_DRM_PROPERTY_TV_BOTTOM_MARGIN           = 5
GUD_DRM_PROPERTY_TV_MODE                    = 6
GUD_DRM_PROPERTY_TV_BRIGHTNESS              = 7
GUD_DRM_PROPERTY_TV_CONTRAST                = 8
GUD_DRM_PROPERTY_TV_FLICKER_REDUCTION       = 9
GUD_DRM_PROPERTY_TV_OVERSCAN                = 10
GUD_DRM_PROPERTY_TV_SATURATION              = 11
GUD_DRM_PROPERTY_TV_HUE                     = 12
GUD_DRM_PROPERTY_BACKLIGHT_BRIGHTNESS       = 13
GUD_DRM_PROPERTY_ROTATION                   = 50

prop_to_name = {
    GUD_DRM_PROPERTY_TV_SELECT_SUBCONNECTOR: 'GUD_DRM_PROPERTY_TV_SELECT_SUBCONNECTOR',
    GUD_DRM_PROPERTY_TV_LEFT_MARGIN: 'GUD_DRM_PROPERTY_TV_LEFT_MARGIN',
    GUD_DRM_PROPERTY_TV_RIGHT_MARGIN: 'GUD_DRM_PROPERTY_TV_RIGHT_MARGIN',
    GUD_DRM_PROPERTY_TV_TOP_MARGIN: 'GUD_DRM_PROPERTY_TV_TOP_MARGIN',
    GUD_DRM_PROPERTY_TV_BOTTOM_MARGIN: 'GUD_DRM_PROPERTY_TV_BOTTOM_MARGIN',
    GUD_DRM_PROPERTY_TV_MODE: 'GUD_DRM_PROPERTY_TV_MODE',
    GUD_DRM_PROPERTY_TV_BRIGHTNESS: 'GUD_DRM_PROPERTY_TV_BRIGHTNESS',
    GUD_DRM_PROPERTY_TV_CONTRAST: 'GUD_DRM_PROPERTY_TV_CONTRAST',
    GUD_DRM_PROPERTY_TV_FLICKER_REDUCTION: 'GUD_DRM_PROPERTY_TV_FLICKER_REDUCTION',
    GUD_DRM_PROPERTY_TV_OVERSCAN: 'GUD_DRM_PROPERTY_TV_OVERSCAN',
    GUD_DRM_PROPERTY_TV_SATURATION: 'GUD_DRM_PROPERTY_TV_SATURATION',
    GUD_DRM_PROPERTY_TV_HUE: 'GUD_DRM_PROPERTY_TV_HUE',
    GUD_DRM_PROPERTY_BACKLIGHT_BRIGHTNESS: 'GUD_DRM_PROPERTY_BACKLIGHT_BRIGHTNESS',
    GUD_DRM_PROPERTY_ROTATION: 'GUD_DRM_PROPERTY_ROTATION',
}


GUD_DRM_COMPRESSION_LZ4     = BIT(0)

class gud_drm_usb_vendor_descriptor(ctypes.LittleEndianStructure):
    _fields_ = [
        ('bLength', ctypes.c_uint8),
        ('bDescriptorType', ctypes.c_uint8),
        ('bVersion', ctypes.c_uint8),
        ('bCompression', ctypes.c_uint8),
        ('bMaxBufferSizeOrder', ctypes.c_uint8),
        ('bmFlags', ctypes.c_uint32),
        ('dwMinWidth', ctypes.c_uint32),
        ('dwMaxWidth', ctypes.c_uint32),
        ('dwMinHeight', ctypes.c_uint32),
        ('dwMaxHeight', ctypes.c_uint32),
        ('bNumFormats', ctypes.c_uint8),
        ('bNumProperties', ctypes.c_uint8),
        ('bNumConnectors', ctypes.c_uint8),
    ]
    _pack_ = 1


class gud_drm_req_property(ctypes.LittleEndianStructure):
    _fields_ = [
        ('prop', ctypes.c_uint16),
        ('val', ctypes.c_uint64),
    ]
    _pack_ = 1


GUD_DRM_CONNECTOR_FLAGS_POLL    = BIT(0)

class gud_drm_req_get_connector(ctypes.LittleEndianStructure):
    _fields_ = [
        ('connector_type', ctypes.c_uint8),
        ('bmFlags', ctypes.c_uint32),
        ('num_properties', ctypes.c_uint8),
    ]
    _pack_ = 1


GUD_DRM_CONNECTOR_STATUS_MASK       = 0xf # Only 2 bits are currently used for status
GUD_DRM_CONNECTOR_STATUS_CHANGED    = BIT(7)

class gud_drm_req_get_connector_status(ctypes.LittleEndianStructure):
    _fields_ = [
        ('status', ctypes.c_uint8),
        ('num_modes', ctypes.c_uint16),
        ('edid_len', ctypes.c_uint16),
    ]
    _pack_ = 1


class gud_drm_req_display_mode(ctypes.LittleEndianStructure):
    _fields_ = [
        ('clock', ctypes.c_uint32),
        ('hdisplay', ctypes.c_uint16),
        ('hsync_start', ctypes.c_uint16),
        ('hsync_end', ctypes.c_uint16),
        ('htotal', ctypes.c_uint16),
        ('hskew', ctypes.c_uint16),
        ('vdisplay', ctypes.c_uint16),
        ('vsync_start', ctypes.c_uint16),
        ('vsync_end', ctypes.c_uint16),
        ('vtotal', ctypes.c_uint16),
        ('vscan', ctypes.c_uint16),
        ('vrefresh', ctypes.c_uint32),
        ('flags', ctypes.c_uint32),
        ('type', ctypes.c_uint8),
    ]
    _pack_ = 1


class gud_drm_req_set_buffer(ctypes.LittleEndianStructure):
    _fields_ = [
        ('x', ctypes.c_uint32),
        ('y', ctypes.c_uint32),
        ('width', ctypes.c_uint32),
        ('height', ctypes.c_uint32),

        ('length', ctypes.c_uint32),
        ('compression', ctypes.c_uint8),
        ('compressed_length', ctypes.c_uint32),
    ]
    _pack_ = 1


class gud_drm_req_set_state(ctypes.LittleEndianStructure):
    _fields_ = [
        ('mode', gud_drm_req_display_mode),
        ('format', ctypes.c_uint32),
        ('connector', ctypes.c_uint8),
        ('num_properties', ctypes.c_uint8),
        # struct gud_drm_req_property properties[];
    ]
    _pack_ = 1


####################################################################################################

class Transfer:
    def __init__(self, urb):
        self.urb = urb
        self.request = urb.setup.bRequest
        self.index = urb.setup.wValue
        self.timestamp = urb.ts_start
        self.data = urb.data
        self.status_urb = None
        # No status request issued on IN transfers
        if urb.dirin:
            self.status = urb.status
        else:
            self.status = -errno.EINPROGRESS

    def add_status(self, urb):
        if not urb.dirin or urb.setup.bRequest != 0:
            raise ValueError('Not a status urb:', urb)
        self.status_urb = urb
        if not (int(urb.data[0]) & GUD_DRM_STATUS_PENDING):
            self.status = - int(urb.data[1])

    def done(self):
        return self.status != -errno.EINPROGRESS

    def duration(self):
        if self.done():
            if self.status_urb:
                return (self.status_urb.ts_end - self.timestamp) * 1000
            else:
                return (self.urb.ts_end - self.timestamp) * 1000
        else:
            return 0

    @property
    def value(self):
        if len(self.data) == 0:
            return ''
        elif len(self.data) == 1:
            return int(self.data[0])
        elif self.request == USB_REQ_GET_DESCRIPTOR and len(self.data) == ctypes.sizeof(gud_drm_usb_vendor_descriptor):
            return gud_drm_usb_vendor_descriptor.from_buffer_copy(self.data)
        elif self.request in (GUD_DRM_USB_REQ_GET_PROPERTIES, GUD_DRM_USB_REQ_GET_CONNECTOR_PROPERTIES):
            num = len(self.data) // ctypes.sizeof(gud_drm_req_property)
            return (gud_drm_req_property * num).from_buffer_copy(self.data)
        elif self.request == GUD_DRM_USB_REQ_GET_CONNECTOR:
            return gud_drm_req_get_connector.from_buffer_copy(self.data)
        elif self.request == GUD_DRM_USB_REQ_GET_CONNECTOR_STATUS:
            return gud_drm_req_get_connector_status.from_buffer_copy(self.data)
        elif self.request == GUD_DRM_USB_REQ_GET_CONNECTOR_MODES:
            num = len(self.data) // ctypes.sizeof(gud_drm_req_display_mode)
            return (gud_drm_req_display_mode * num).from_buffer_copy(self.data)
        elif self.request == GUD_DRM_USB_REQ_SET_MODE_CHECK:
            sz = ctypes.sizeof(gud_drm_req_set_state)
            val = gud_drm_req_set_state.from_buffer_copy(self.data[:sz])
            val.properties = (gud_drm_req_property * val.num_properties).from_buffer_copy(self.data[sz:])
            return val
        else:
            return self.data

    def props_to_str(self, props):
        s = ''
        for prop in props:
            name = prop_to_name.get(prop.prop, f'{prop.prop}')
            s += f'    {name} = {prop.val}'
            if prop.val > 9:
                s += f' (0x{prop.val:x})'
            s += f'\n'
        return s

    def __str__(self):
        name = req_to_name.get(self.request, f'{self.request:02x}')
        s = f'{name}:'
        if self.status == 0:

            if self.request == USB_REQ_GET_DESCRIPTOR and len(self.data) == ctypes.sizeof(gud_drm_usb_vendor_descriptor):
                s += f'\n'
                s += f'    version={self.value.bVersion}\n'
                s += f'    compression=0x{self.value.bCompression:x}\n'
                s += f'    MaxBufferSizeOrder={self.value.bMaxBufferSizeOrder}\n'
                s += f'    bmFlags=0x{self.value.bmFlags:x}\n'
                s += f'    MinWidth={self.value.dwMinWidth}\n'
                s += f'    MaxWidth={self.value.dwMaxWidth}\n'
                s += f'    MinHeight={self.value.dwMinHeight}\n'
                s += f'    MaxHeight={self.value.dwMaxHeight}\n'
                s += f'    NumFormats={self.value.bNumFormats}\n'
                s += f'    NumProperties={self.value.bNumProperties}\n'
                s += f'    NumConnectors={self.value.bNumConnectors}\n'
                s += '   '

            elif self.request == GUD_DRM_USB_REQ_GET_FORMATS:
                s += f' {self.value}'

            elif self.request in (GUD_DRM_USB_REQ_GET_PROPERTIES, GUD_DRM_USB_REQ_GET_CONNECTOR_PROPERTIES):
                s += f'\n'
                s += self.props_to_str(self.value)
                s += '   '

            elif self.request == GUD_DRM_USB_REQ_GET_CONNECTOR:
                s += f' index={self.index}'
                s += f' type={self.value.connector_type}'
                s += f' flags={self.value.bmFlags:x}'
                s += f' num_properties={self.value.num_properties}'

            elif self.request == GUD_DRM_USB_REQ_GET_CONNECTOR_STATUS:
                value = self.value
                s += f' index={self.index}'
                status = value.status & GUD_DRM_CONNECTOR_STATUS_MASK
                sn = {1: 'connected', 2: 'disconnected', 3: 'unknown'}.get(status, None)
                if sn is None:
                    sn = f'ILLEGAL:{status}'
                s += f' status={sn}'
                if value.status & GUD_DRM_CONNECTOR_STATUS_CHANGED:
                    s += ' (CHANGED)'
                s += f' num_modes={value.num_modes}'
                s += f' edid_len={value.edid_len}'

            elif self.request == GUD_DRM_USB_REQ_GET_CONNECTOR_MODES:
                s += f'\n'
                for mode in self.value:
                    s += f'    mode={mode.hdisplay}x{mode.vdisplay}@{mode.vrefresh}\n'
                s += '   '

            elif self.request == GUD_DRM_USB_REQ_GET_CONNECTOR_EDID:
                s += f' len={len(self.value)}'

            elif self.request == GUD_DRM_USB_REQ_SET_MODE_CHECK:
                mode = self.value.mode
                s += f' mode={mode.hdisplay}x{mode.vdisplay}@{mode.vrefresh}'
                formatname = bytes.fromhex(f'{self.value.format:x}').decode("ascii")[::-1]
                s += f' format={formatname}'
                s += f' connector={self.value.connector}'
                s += f' properties:\n'
                if self.value.num_properties:
                    s += self.props_to_str(self.value.properties)
                s += '   '

            else:
                try:
                    value = self.value.hex()
                except AttributeError:
                    value = self.value
                s += f' {value}'
        else:
            s += f' status={self.status} data={self.data.hex()}'
        s += f' ({self.duration():.1f} ms)'

        return s


class Flush:
    def __init__(self, ctrl, bulk):
        self.ctrl = ctrl
        self.bulk = bulk
        self.value = gud_drm_req_set_buffer.from_buffer_copy(ctrl.data)
        self.duration = (self.bulk.ts_end - self.ctrl.timestamp) * 1000 # includes the time between URBs

    def __str__(self):
        s = f'Flush: '
        s += f'{self.value.width}x{self.value.height}+{self.value.x}+{self.value.y} '
        s += f'length={self.value.length}'
        if self.value.compression:
            s += f'/{self.value.compressed_length} '
            s += f'({(self.value.length / self.value.compressed_length):.1f})'

        bulk_duration = (self.bulk.ts_end - self.bulk.ts_start) * 1000
        s += f' ({self.ctrl.duration():5.1f} + {bulk_duration:.1f} = {self.duration:5.1f} ms)'

        return s


class FlushStat:
    def __init__(self, flush):
        self.prev = None
        self.next = None

        self.ctrl_start = flush.ctrl.timestamp
        self.ctrl_end = flush.ctrl.status_urb.ts_end
        self.bulk_start = flush.bulk.ts_start
        self.bulk_end = flush.bulk.ts_end

        self.x = flush.value.x
        self.y = flush.value.y
        self.width = flush.value.width
        self.height = flush.value.height

        self.len = flush.value.length
        self.len_compressed = flush.value.compressed_length
        if flush.value.compression:
            self.compression = flush.value.length / flush.value.compressed_length
        else:
            self.compression = 1.0

    @property
    def waited(self):
        """Returns true if the update had to wait for the previous one to finish"""
        # On Pi4 a non-wait is 0.6-0.7 ms, the first status poll wait is >0.5ms
        return (self.ctrl_end - self.ctrl_start) > 0.001 # 1ms

    @property
    def start(self):
        if self.waited:
            return self.ctrl_end
        else:
            return self.ctrl_start

    @property
    def end(self):
        if self.next and self.next.waited:
            return self.next.ctrl_end
        return self.bulk_end

    @property
    def duration(self):
        return (self.end - self.start) * 1000

    def __str__(self):
        return f'{self.width}x{self.height}+{self.x}+{self.y}: start={self.start:.3f} end={self.end:.3f} duration={self.duration:.1f} ms'


class Stats:
    def __init__(self):
        self.updates = []
        self.width = 0
        self.height = 0

    def add(self, flush):
        stat = FlushStat(flush)
        width = stat.x + stat.width
        if width > self.width:
            self.width = width
        height = stat.y + stat.height
        if height > self.height:
            self.height = height

        if self.updates:
            prev = self.updates[-1]
            stat.prev = prev
            prev.next = stat

        self.updates.append(stat)

    def full(self):
        # Full updates might be split because device buffer is too small
        # Merge the partials if any
        full = []
        merge = None
        for s in self.updates:
            if s.x == 0 and s.y == 0 and s.width == self.width and s.height == self.height:
                full.append(s)
                merge = None
                continue

            if s.x != 0 or s.width != self.width:
                merge = None
                continue

            if s.y == 0:
                merge = [s]
                continue
            if not merge:
                continue

            if s.y != (merge[-1].y + merge[-1].height):
                merge = None
                continue

            merge.append(s)

            if (s.y + s.height) == self.height:
                n = copy.copy(merge[0])
                n.width, n.height = self.width, self.height
                n.compression = sum([x.compression for x in merge]) / len(merge)
                n.bulk_end = merge[-1].bulk_end
                full.append(n)
                merge = None

        return full

    def group_by_size(self):
        # Python 3.7 dict is ordered
        d = {}
        for i in self.updates:
            k = i.width * i.height
            if k not in d:
                d[k] = []
            d[k].append(i)
        return {k:d[k] for k in sorted(d.keys(), reverse=True)}

    def __str__(self):
        if not self.updates:
            return '<none>'

        #print()
        #print()
        #print()
        #for s in self.updates:
        #    print(s)
        #print()
        #print()
        #print()

        def stat_str(lst):
            minimum = min([x.duration for x in lst])
            maximum = max([x.duration for x in lst])
            average = sum([x.duration for x in lst]) / len(lst)
            return f'        {lst[0].width}x{lst[0].height}: {minimum:.1f} < {average:.1f} ms < {maximum:.1f} ({len(lst):d})\n'

        s = 'Statistics:\n'

        g = self.group_by_size()

        s += '    Rects:\n'
        for sz in g.values():
            s += stat_str(sz)

        full = self.full()
        if full:
            s += '    Full:\n'
            s += stat_str(full)
            #fps = 1000.0 / (sum([x.duration for x in full]) / len(full))
            #s += f'        fps = {fps:.1f}\n'

        if (len(self.updates) > 1):
            s += f'    Totals ({len(self.updates)}):\n'
            first = self.updates[0]
            last = self.updates[-1]
            total_time = last.bulk_end - first.ctrl_start
            total_len = sum([x.len for x in self.updates])
            total_compressed_len = sum([x.len_compressed if x.len_compressed else x.len for x in self.updates])

            s += f'        time: {int(total_time)} seconds\n'

            compression = total_len / total_compressed_len
            s += f'        compression: {compression:.1f}\n'

            throughput = total_len / total_time
            s += '        throughput: '
            if throughput < 1024:
                s += f'{int(throughput)} B/s'
            elif throughput < 1024 * 1024:
                s += f'{(throughput / 1024):.1f} kB/s'
            else:
                s += f'{(throughput / 1024 / 1024):.1f} MB/s'
            s +=  '\n'

            cpp = first.len / (first.width * first.height)
            total_frame_length = self.width *self.height * cpp
            s += f'        fps={(total_len / total_frame_length / total_time):.1f}\n'

        return s


####################################################################################################


def monitor(busnum, devnum=None, debug=False):
    devstr = f'{devnum:03d}' if devnum else 'DISCOVER'
    print(f'Monitoring: {busnum:03d}:{devstr}\n')

    # mon_bin_event(): Max stored URB length is: bufsize / 5
    # Keep kernel buffer small to avoid excess copying from framebuffer transfers, we don't need the pixels
    bufsize = 20 * 1024 # PAGE_SIZE=4k aligned

    def drop_cb(hdr, reason, dropped):
        print(f'DROP: {reason} (dropped={dropped}):')
        print(f'    {hdr}')

    transfer = None
    control_flush = None
    flush = None

    stats = Stats()

    for urb in USBmon(busnum, bufsize, debug > 1, drop_cb):

        # Look for the display descriptor if DISCOVER
        if (devnum is None and urb.type == PIPE_CONTROL and
            urb.setup.bRequest == USB_REQ_GET_DESCRIPTOR and
            urb.setup.bRequestType == (USB_DIR_IN | USB_TYPE_VENDOR | USB_RECIP_INTERFACE) and
            urb.setup.wValue == (GUD_DRM_USB_DT_INTERFACE << 8) and
            urb.len == ctypes.sizeof(gud_drm_usb_vendor_descriptor)
        ):
            devnum = urb.devnum
            print(f'\nMonitoring: {busnum:03d}:{devnum:03d}\n')

        if debug:
            print(urb)

        if urb.devnum != devnum:
            continue

        if urb.type == PIPE_CONTROL:
            if urb.setup.bRequest == 0:
                if transfer:
                    transfer.add_status(urb)
                else:
                    print('Dangling status urb:', urb)
                    continue
            else:
                transfer = Transfer(urb)

            if transfer.done():
                if transfer.request == GUD_DRM_USB_REQ_SET_BUFFER:
                    control_flush = transfer
                else:
                    print(transfer)
                    if debug:
                        print()
                transfer = None

        elif urb.type == PIPE_BULK:
            if control_flush:
                flush = Flush(control_flush, urb)
                control_flush = None
            else:
                print('Dangling bulk urb:', urb)

        elif not debug:
            print(urb)

        if flush:
            print(flush)
            stats.add(flush)
            if debug:
                print()
            flush = None

    print()
    print(stats)


def main(vid, pid, busnum, debug):
    p = '/dev/usbmon0'
    try:
        open(p)
    except FileNotFoundError:
        print(f'ERROR: {p} is not found, is usbmon loaded?')
        return
    except PermissionError:
        print(f'ERROR: {p} is not accessible, not root?')
        return

    if busnum is None:
        print('Looking for device...')
        dev = usb.core.find(idVendor=vid, idProduct=pid)
        if not dev:
            print(f'No device found for: {vid:03x}:{pid:03x}')
            return
        print(f'Found: {dev.product}')
        busnum = dev.bus
        devnum = dev.address
    else:
        devnum = None

    monitor(busnum, devnum, debug)


def device_arg_split(arg):
    vid, pid = str(arg).split(':')
    return int(vid, 16), int(pid, 16)


def device_arg_check(arg):
    try:
        device_arg_split(arg)
    except Exception:
        raise argparse.ArgumentTypeError('Value has to be on the form: vid:pid')
    return arg


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='GUD USB monitor')
    parser.add_argument('--debug', '-d', action='count', default=0, help='increase debug output')
    parser.add_argument('busnum', nargs='?', type=int, help='USB busnum when monitoring before device plugin')
    parser.add_argument('--device', '-D', type=device_arg_check, help='Device to monitor: vid:pid (in hexadecimal) default=1d50:6150', default='1d50:6150')

    args = parser.parse_args()
    vid, pid = device_arg_split(args.device)

    main(vid, pid, args.busnum, args.debug)
