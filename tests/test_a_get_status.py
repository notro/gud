import pytest
import ctypes
import errno
import usb.core
from gud import *

@pytest.fixture(autouse=True, scope='session')
def ensure_status_is_zero(dev):
    dev.gud_usb_control_msg(True, GUD_REQ_GET_DESCRIPTOR, 0, ctypes.sizeof(ctypes.c_uint32))


def test_get_status(dev):
    assert dev.req_get_status() == 0

def test_get_status_multiple(dev):
    for _ in range(10):
        assert dev.req_get_status() == 0

# Linux stalls, extra code would be needed to return zero, not worth it just to have this test
def XXXtest_get_status_short(dev):
    with pytest.raises(usb.core.USBError) as exc_info:
        dev.gud_usb_control_msg(True, GUD_REQ_GET_STATUS, 0, None)
    assert exc_info.value.errno == errno.EPIPE

def test_get_status_long(dev):
    buf = bytearray(2)
    ret = dev.gud_usb_control_msg(True, GUD_REQ_GET_STATUS, 0, buf)
    assert len(ret) == 1
    assert ctypes.c_uint8.from_buffer_copy(ret).value == 0

@pytest.mark.stall
def test_get_status_wrong_wValue(dev):
    buf = bytearray(1)
    with pytest.raises(usb.core.USBError) as exc_info:
        dev.gud_usb_control_msg(True, GUD_REQ_GET_STATUS, 1, buf)
    assert exc_info.value.errno == errno.EPIPE

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

@pytest.mark.stall
def test_get_status_out_should_fail(dev):
    with pytest.raises(usb.core.USBError) as exc_info:
        dev.gud_usb_control_msg(False, GUD_REQ_GET_STATUS, 0, 1)
    assert exc_info.value.errno == errno.EPIPE
