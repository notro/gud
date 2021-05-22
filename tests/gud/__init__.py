from .gud_h import *
from .image import *

import errno

import usb.core
import usb.util

class GUDBaseException(Exception):
    @classmethod
    def from_status(cls, status):
#        if cls is GUDBaseException:
        if status == GUD_STATUS_OK:
            raise ValueError('status is OK')
        sub = GUDBaseException.subclasses.get(status, GUDError)
        print('sub:', sub)
        return sub(status)
#        else:
#            return Exception()

    def __init__(self, status):
        self.status = status

class GUDBusyError(GUDBaseException):
    pass

class GUDReqNotSupportedError(GUDBaseException):
    pass

class GUDProtocolError(GUDBaseException):
    pass

class GUDInvalidParameterError(GUDBaseException):
    pass

class GUDError(GUDBaseException):
    pass

GUDBaseException.subclasses = {
    GUD_STATUS_BUSY: GUDBusyError,
    GUD_STATUS_REQUEST_NOT_SUPPORTED: GUDReqNotSupportedError,
    GUD_STATUS_PROTOCOL_ERROR: GUDProtocolError,
    GUD_STATUS_INVALID_PARAMETER: GUDInvalidParameterError,
    GUD_STATUS_ERROR: GUDError,
}


class Property(object):
    def __init__(self, req):
        self.prop = req.prop
        if self.prop == GUD_PROPERTY_ROTATION:
            self.mask = req.val
            self.val = GUD_ROTATION_0
        else:
            self.mask = None
            self.val = req.val

    def __repr__(self):
        return f'Property({property_to_str(self.prop)}={self.val}(0x{self.val:x})'


class Connector(object):
    def __init__(self, dev, index, req):
        self.dev = dev
        self.index = index
        self.req = req
        self.type = req.connector_type
        self.flags = req.flags
        self._status = GUD_CONNECTOR_STATUS_UNKNOWN
        self.modes = None
        self.edid = None
        self._properties = None

    def update(self, force=False):
        status = self.dev.req_get_connector_status(self)
        changed = status & GUD_CONNECTOR_STATUS_CHANGED
        if changed or self._status != status:
            self.modes = self.dev.req_get_connector_modes(self)
            self.edid = self.dev.req_get_connector_edid(self)
        self._status = status

    @property
    def status(self):
        return self._status & GUD_CONNECTOR_STATUS_CONNECTED_MASK

    @property
    def connected(self):
        return self.status == GUD_CONNECTOR_STATUS_CONNECTED

    @property
    def properties(self):
        if self._properties:
            return self._properties

        reqs = self.dev.req_get_connector_properties(self)
        properties = []
        for req in reqs:
            properties.append(Property(req))

        self._properties = properties
        return properties

    def set(self, prop, val):
        for p in self.properties:
            if p.prop == prop:
                p.val = val
                break

    def type_to_str(self):
        connector_type_to_name = {
            GUD_CONNECTOR_TYPE_PANEL: 'Panel',
            GUD_CONNECTOR_TYPE_VGA: 'VGA',
            GUD_CONNECTOR_TYPE_COMPOSITE: 'Composite',
            GUD_CONNECTOR_TYPE_SVIDEO: 'S-Video',
            GUD_CONNECTOR_TYPE_COMPONENT: 'Component',
            GUD_CONNECTOR_TYPE_DVI: 'DVI',
            GUD_CONNECTOR_TYPE_DISPLAYPORT: 'DisplayPort',
            GUD_CONNECTOR_TYPE_HDMI: 'HDMI',
        }
        return f'{connector_type_to_name.get(self.type, "Unknown")}'

    def flag_to_str(self, flag):
        flag_to_name = {
            GUD_CONNECTOR_FLAGS_POLL_STATUS : 'GUD_CONNECTOR_FLAGS_POLL_STATUS',
            GUD_CONNECTOR_FLAGS_INTERLACE : 'GUD_CONNECTOR_FLAGS_INTERLACE',
            GUD_CONNECTOR_FLAGS_DOUBLESCAN : 'GUD_CONNECTOR_FLAGS_DOUBLESCAN',
        }
        return f'{flag_to_name.get(flag, "Unknown")}'

    def status_to_str(self):
        connector_status_to_name = {
            GUD_CONNECTOR_STATUS_DISCONNECTED: 'disconnected',
            GUD_CONNECTOR_STATUS_CONNECTED: 'connected',
            GUD_CONNECTOR_STATUS_UNKNOWN: 'unknown',
        }
        return f'{connector_status_to_name.get(self.status, "out-of-bounds")}'

    def __repr__(self):
        flags = [2**i for i, v in enumerate(bin(self.flags)[:1:-1]) if int(v)][::-1]
        flags_str = ', '.join([self.flag_to_str(f) for f in flags])
        s = f'Connector(index={self.index}, type={self.type_to_str()}, flags=[{flags_str}])'
        if self._properties:
            s += f', properties=['
            s += ', '.join([f'{prop}' for prop in self._properties])
            s += ']'
        return s + f', status={self.status_to_str()})'


class State(object):
    def __init__(self, dev, mode=None, fmt=None, connector=None):
        if fmt is None:
            fmt = dev.formats[0]
        if connector is None:
            connector = dev.connectors[0]
        if mode is None:
            mode = connector.modes[0]
        self.dev = dev
        self.mode = mode
        self.format = fmt
        self.connector = connector

    @property
    def vrefresh(self):
        num = self.mode.clock
        den = self.mode.htotal * self.mode.vtotal

        if self.mode.flags & GUD_DISPLAY_MODE_FLAG_INTERLACE:
            num *= 2
        if self.mode.flags & GUD_DISPLAY_MODE_FLAG_DBLSCAN:
            den *= 2

        return num * 1000 // den

    def check(self):
        props = self.dev.properties + self.connector.properties
        req = define_gud_drm_req_set_state(len(props))()
        for index, prop in enumerate(props):
            req.properties[index].prop = prop.prop
            req.properties[index].val = prop.val
        req.mode = self.mode
        req.format = self.format
        req.connector = self.connector.index
        self.dev.req_set_state_check(req)

    def commit(self):
        self.dev.req_set_state_commit()

    def __str__(self):
        return f'{self.mode.hdisplay}x{self.mode.vdisplay}-{self.vrefresh}@{format_to_name(self.format)}'

class Device(object):
    def __init__(self, dev):
        self.dev = dev
        self._descriptor = None
        self._formats = None
        self._properties = None
        self._connectors = None
        self.state = None

    def config(self):
        self.dev.set_configuration()
        cfg = self.dev.get_active_configuration()
        self.interface = cfg[(0,0)]
        self.ep = usb.util.find_descriptor(
            self.interface,
            # match the first OUT endpoint
            custom_match = lambda e: usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_OUT)
        assert self.ep is not None

    def _get_ifnum(self, ifnum):
        if ifnum is None:
            if self.interface:
                return self.interface.bInterfaceNumber
            else:
                return 0
        else:
            return ifnum

    def reset(self):
        self.dev.reset()

    def is_kernel_driver_active(self, ifnum=None):
        return self.dev.is_kernel_driver_active(self._get_ifnum(ifnum))

    def detach_kernel_driver(self, ifnum=None):
        self.dev.detach_kernel_driver(self._get_ifnum(ifnum))

    def attach_kernel_driver(self, ifnum=None):
        self.dev.attach_kernel_driver(self._get_ifnum(ifnum))

    @property
    def descriptor(self):
        if self._descriptor:
            return self._descriptor
        self._descriptor = self.req_get_descriptor()
        return self._descriptor

    @property
    def flags(self):
        return self.descriptor.flags

    @property
    def max_buffer_size(self):
        # The host driver maxes out at 4MB (kmalloc limit)
        if self.descriptor.max_buffer_size:
            return min(self.descriptor.max_buffer_size, 4 * 1024 * 1024)
        else:
            return 4 * 1024 * 1024

    def status(self):
        return self.req_get_status()

    def status_to_str(self, status):
        status_to_name = {
            GUD_STATUS_OK: 'GUD_STATUS_OK',
            GUD_STATUS_BUSY: 'GUD_STATUS_BUSY',
            GUD_STATUS_REQUEST_NOT_SUPPORTED: 'GUD_STATUS_REQUEST_NOT_SUPPORTED',
            GUD_STATUS_PROTOCOL_ERROR: 'GUD_STATUS_PROTOCOL_ERROR',
            GUD_STATUS_INVALID_PARAMETER: 'GUD_STATUS_INVALID_PARAMETER',
            GUD_STATUS_ERROR: 'GUD_STATUS_ERROR',
        }
        if status > GUD_STATUS_ERROR:
            status = GUD_STATUS_ERROR
        return f'{status_to_name.get(status)}'

    @property
    def formats(self):
        if self._formats:
            return self._formats

        self._formats = self.req_get_formats()
        return self._formats

    @property
    def properties(self):
        if self._properties:
            return self._properties

        reqs = self.req_get_properties()
        properties = []
        for req in reqs:
            properties.append(Property(req))

        self._properties = properties
        return properties

    def set(self, prop, val):
        for p in self.properties:
            if p.prop == prop:
                p.val = val
                break

    @property
    def connectors(self):
        if self._connectors:
            return self._connectors

        reqs = self.req_get_connectors()
        connectors = []
        for (index, req) in enumerate(reqs):
            connectors.append(Connector(self, index, req))
        self._connectors = connectors
        return connectors

    def enable(self):
        self.req_set_display_enable(1)

    def disable(self):
        self.req_set_display_enable(0)

    def controller_enable(self):
        self.req_set_controller_enable(1)

    def controller_disable(self):
        self.req_set_controller_enable(0)

    def commit(self, state):
        state.check()
        state.commit()
        if self.state is None:
            self.enable()
        self.state = state

    def __enter__(self):
        self.controller_enable()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disable()
        self.controller_disable()

    def __str__(self):
        return f'{self.dev}'

    def gud_usb_control_msg(self, _in, request, value, buf):
        requesttype = usb.util.CTRL_TYPE_VENDOR | usb.util.CTRL_RECIPIENT_INTERFACE;
        if _in:
            requesttype |= usb.util.CTRL_IN;

        return self.dev.ctrl_transfer(requesttype, request, value, self.interface.bInterfaceNumber,
                                      data_or_wLength = buf, timeout = None)

    def gud_usb_transfer(self, _in, request, index, buf):
        #drm_dbg(&gdrm->drm, "%s: request=0x%x index=%u len=%zu\n",
        #    _in ? "get" : "set", request, index, len)

        stall = False

        try:
            ret = self.gud_usb_control_msg(_in, request, index, buf)
        except usb.core.USBError as e:
            if e.errno == errno.EPIPE:
                stall = True
            else:
                raise e from None

        if stall or ((self.flags & GUD_DISPLAY_FLAG_STATUS_ON_SET) and not _in):
            status = self.status()
            if stall and not status:
                raise ValueError('status returned OK on stall')
            if status:
                print(f'ERROR: {status} {self.status_to_str(status)}')
                raise GUDBaseException.from_status(status)
        return ret;

    def gud_usb_get(self, request, index, buf):
        return self.gud_usb_transfer(True, request, index, buf);

    def gud_usb_set(self, request, index, buf):
        ret = self.gud_usb_transfer(False, request, index, buf);
        if buf and ret != len(buf):
            raise "error"
        return ret


    '''
    def gud_usb_get_u8(self, request, index, val):
        ret = self.gud_usb_get(request, index, buf, sizeof(*val))
        *val = *buf
        if (ret < 0)
            return ret;

        return ret != sizeof(*val) ? -EIO : 0

    def gud_usb_set_u8(self, request, val):
        return self.usb_set(request, 0, &val, sizeof(val))


'''

    def req_get_status(self):
        buf = bytearray(1)
        ret = self.gud_usb_control_msg(True, GUD_REQ_GET_STATUS, 0, buf)
        if len(ret) != len(buf):
            return None;
        return ctypes.c_uint8.from_buffer_copy(ret).value

    def req_get_descriptor(self):
        buf = bytearray(ctypes.sizeof(gud_drm_usb_vendor_descriptor))
        ret = self.gud_usb_control_msg(True, GUD_REQ_GET_DESCRIPTOR, 0, buf)

        if len(ret) != len(buf):
            return None;

        desc = gud_drm_usb_vendor_descriptor.from_buffer_copy(ret)

        if desc.magic != GUD_DISPLAY_MAGIC:
            return None;

        if desc.version == 0 or desc.max_width == 0 or desc.max_height == 0 or \
           desc.min_width > desc.max_width or desc.min_height > desc.max_height:
            return None;

        return desc;

    def req_get_formats(self):
        buf = bytearray(GUD_FORMATS_MAX_NUM)
        return tuple(self.gud_usb_get(GUD_REQ_GET_FORMATS, 0, buf))

    def req_get_array(self, request, index, cls, max_num):
        buf = bytearray(ctypes.sizeof(cls) * max_num)
        ret = self.gud_usb_get(request, index, buf)

        if len(ret) % ctypes.sizeof(cls):
            raise

        num = len(ret) // ctypes.sizeof(cls)
        return (cls * num).from_buffer_copy(ret)

    def req_get_properties(self):
        return self.req_get_array(GUD_REQ_GET_PROPERTIES, 0, gud_drm_req_property, GUD_PROPERTIES_MAX_NUM)

    def req_get_connectors(self):
        return self.req_get_array(GUD_REQ_GET_CONNECTORS, 0, gud_drm_req_get_connector, GUD_CONNECTORS_MAX_NUM)

    def req_get_connector_properties(self, connector):
        return self.req_get_array(GUD_REQ_GET_CONNECTOR_PROPERTIES, connector.index, gud_drm_req_property, GUD_CONNECTOR_PROPERTIES_MAX_NUM)

    def req_get_connector_tv_mode_values(self):
        pass

    def req_set_connector_force_detect(self):
        pass

    def req_get_connector_status(self, connector):
        buf = bytearray(1)
        ret = self.gud_usb_get(GUD_REQ_GET_CONNECTOR_STATUS, connector.index, buf)
        if len(ret) != len(buf):
            return None;
        return ctypes.c_uint8.from_buffer_copy(ret).value

    def req_get_connector_modes(self, connector):
        return self.req_get_array(GUD_REQ_GET_CONNECTOR_MODES, connector.index, gud_drm_req_display_mode, GUD_CONNECTOR_MAX_NUM_MODES)

    def req_get_connector_edid(self, connector):
        buf = bytearray(GUD_CONNECTOR_MAX_EDID_LEN)
        ret = self.gud_usb_get(GUD_REQ_GET_CONNECTOR_EDID, connector.index, buf)
        if len(ret) % 128:
            return None;
        return bytes(ret)

    def req_set_buffer(self, req):
        self.gud_usb_set(GUD_REQ_SET_BUFFER, 0, bytearray(req))

    def req_set_state_check(self, req):
        self.gud_usb_set(GUD_REQ_SET_STATE_CHECK, 0, bytearray(req))

    def req_set_state_commit(self):
        self.gud_usb_set(GUD_REQ_SET_STATE_COMMIT, 0, None)

    def req_set_controller_enable(self, val):
        self.gud_usb_set(GUD_REQ_SET_CONTROLLER_ENABLE, 0, bytearray((val,)))

    def req_set_display_enable(self, val):
        self.gud_usb_set(GUD_REQ_SET_DISPLAY_ENABLE, 0, bytearray((val,)))

    def bulk_write(self, buf, length):
        ret = self.dev[0].interfaces()[0].endpoints()[0].write(buf, length)
        assert ret == len(buf)


def find(find_all=False, **args):
    def is_vendor(dev):
        import usb.util
        for cfg in dev:
            if usb.util.find_descriptor(cfg, bInterfaceClass=0xff) is not None:
                return True

    def device_iter(**kwargs):
        for dev in usb.core.find(find_all=True, custom_match = is_vendor, **kwargs):
            d = Device(dev)
            yield d

    if find_all:
        return device_iter(**args)
    else:
        try:
            return next(device_iter(**args))
        except StopIteration:
            return None

def find_first_setup():
    dev = find()
    if not dev:
        return None
    if dev.is_kernel_driver_active(0):
        dev.detach_kernel_driver(0)
    dev.reset()
    dev.config()
    for connector in dev.connectors:
        connector.update()
    return dev
