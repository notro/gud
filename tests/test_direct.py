# SPDX-License-Identifier: CC0-1.0

import pytest
import ctypes
import usb.core
from gud import *


@pytest.fixture(name='dev', scope='session')
def gud_device():
    dev = find()
    if not dev:
        raise "No device"
    if dev.is_kernel_driver_active():
        dev.detach_kernel_driver()
    return dev

@pytest.fixture(scope='module')
def ensure_status_is_zero(dev):
    dev.gud_usb_control_msg(True, GUD_REQ_GET_DESCRIPTOR, 0, ctypes.sizeof(ctypes.c_uint32))


def test_get_status(dev):
    assert dev.req_get_status() == 0

def test_get_status_multiple(dev):
    for _ in range(10):
        assert dev.req_get_status() == 0

@pytest.mark.stall
def test_get_status_req_not_supported(dev):
    with pytest.raises(usb.core.USBError) as exc_info:
        dev.gud_usb_control_msg(True, GUD_REQ_UNSUPPORTED, 0, 1)
    assert exc_info.value.errno == errno.EPIPE
    # Device should not clear status when read
    for _ in range(2):
        assert dev.req_get_status() == GUD_STATUS_REQUEST_NOT_SUPPORTED

@pytest.mark.stall
def test_get_status_cleared_after_success(dev):
    with pytest.raises(usb.core.USBError) as exc_info:
        dev.gud_usb_control_msg(True, GUD_REQ_UNSUPPORTED, 0, 1)
    assert exc_info.value.errno == errno.EPIPE
    assert dev.req_get_status() == GUD_STATUS_REQUEST_NOT_SUPPORTED
    # Clear status
    dev.gud_usb_control_msg(True, GUD_REQ_GET_DESCRIPTOR, 0, ctypes.sizeof(ctypes.c_uint32))
    assert dev.req_get_status() == 0


def check_formats(formats):
    for fmt in formats:
        try:
            val = fmt.value
        except AttributeError:
            val = fmt
        assert val in (GUD_PIXEL_FORMAT_R1, GUD_PIXEL_FORMAT_XRGB1111, GUD_PIXEL_FORMAT_RGB565,
                       GUD_PIXEL_FORMAT_XRGB8888, GUD_PIXEL_FORMAT_ARGB8888,)

def check_properties(props):
    if len(props) == 0:
        return
    assert len(props) == 1
    assert props[0].prop == GUD_PROPERTY_ROTATION
    assert (props[0].val & (~GUD_ROTATION_MASK & 0xff)) == 0

def check_connector_properties(props):
    for prop in props:
        assert prop.prop in (GUD_PROPERTY_TV_LEFT_MARGIN, GUD_PROPERTY_TV_RIGHT_MARGIN,
                             GUD_PROPERTY_TV_TOP_MARGIN, GUD_PROPERTY_TV_BOTTOM_MARGIN,
                             GUD_PROPERTY_TV_MODE, GUD_PROPERTY_TV_BRIGHTNESS,
                             GUD_PROPERTY_TV_CONTRAST, GUD_PROPERTY_TV_FLICKER_REDUCTION,
                             GUD_PROPERTY_TV_OVERSCAN, GUD_PROPERTY_TV_SATURATION,
                             GUD_PROPERTY_TV_HUE, GUD_PROPERTY_BACKLIGHT_BRIGHTNESS)


def test_get_descriptor_magic_only(dev):
    buf = bytearray(ctypes.sizeof(ctypes.c_uint32))
    ret = dev.gud_usb_control_msg(True, GUD_REQ_GET_DESCRIPTOR, 0, buf)
    assert len(ret) == len(buf)
    assert ctypes.c_uint32.from_buffer_copy(ret).value == GUD_DISPLAY_MAGIC


@pytest.fixture(name='gud', scope='session')
def gud_device_ready(dev):
    for connector in dev.connectors:
        connector.update()
    return dev

@pytest.fixture()
def state(gud): #, update_connectors):
    s = State(gud)
    s.check()
    s.commit()
    return s

@pytest.mark.parametrize("req,typ,num,check", [
    (GUD_REQ_GET_DESCRIPTOR, gud_drm_usb_vendor_descriptor, 2, None),
    (GUD_REQ_GET_FORMATS, ctypes.c_uint8, GUD_FORMATS_MAX_NUM, check_formats),
    (GUD_REQ_GET_PROPERTIES, gud_drm_req_property, GUD_PROPERTIES_MAX_NUM, check_properties),
    (GUD_REQ_GET_CONNECTORS, gud_drm_req_get_connector, GUD_CONNECTORS_MAX_NUM, None),
    (GUD_REQ_GET_CONNECTOR_PROPERTIES, gud_drm_req_property, GUD_CONNECTOR_PROPERTIES_MAX_NUM, check_connector_properties),
    #(GUD_REQ_GET_CONNECTOR_TV_MODE_VALUES, ),
    (GUD_REQ_GET_CONNECTOR_STATUS, ctypes.c_uint8, 1, None),
    (GUD_REQ_GET_CONNECTOR_MODES, gud_drm_req_display_mode, GUD_CONNECTOR_MAX_NUM_MODES, None),
    (GUD_REQ_GET_CONNECTOR_EDID, ctypes.c_uint8 * 128, 2048 // 128, None),
])
class TestReqGet:
    def test_all(self, gud, req, typ, num, check):
        buf = bytearray(ctypes.sizeof(typ) * num)
        ret = gud.gud_usb_get(req, 0, buf)
        assert len(ret) == 0 or not len(ret) % ctypes.sizeof(typ)
        if check and len(ret):
            num = len(ret) // ctypes.sizeof(typ)
            reqs = (typ * num).from_buffer_copy(ret)
            check(reqs)

    # Read only one block/struct from a possible array
    def test_one(self, gud, req, typ, num, check):
        buf = bytearray(ctypes.sizeof(typ))
        ret = gud.gud_usb_get(req, 0, buf)
        assert len(ret) == 0 or len(ret) == len(buf)
        if check and len(ret):
            req = typ.from_buffer_copy(ret)
            check([req])
