import pytest
import ctypes
import errno
from gud import *


#@pytest.fixture(autouse=True)
#def slow_down_tests():
#    yield
#    import time
#    time.sleep(1)


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

@pytest.mark.parametrize("req,length", [
    (GUD_REQ_GET_DESCRIPTOR, ctypes.sizeof(ctypes.c_uint32)),
    (GUD_REQ_GET_FORMATS, 1),
    (GUD_REQ_GET_PROPERTIES, ctypes.sizeof(gud_drm_req_property)),
])
@pytest.mark.stall
def test_req_illegal_wValue(gud, req, length):
    with pytest.raises(GUDProtocolError):
        gud.gud_usb_get(req, 1, length)

@pytest.mark.parametrize("req,typ", [
    (GUD_REQ_GET_CONNECTORS, gud_drm_req_get_connector),
    (GUD_REQ_GET_CONNECTOR_PROPERTIES, gud_drm_req_property),
    #(GUD_REQ_GET_CONNECTOR_TV_MODE_VALUES, ),
    (GUD_REQ_GET_CONNECTOR_STATUS, ctypes.c_uint8),
    (GUD_REQ_GET_CONNECTOR_MODES, gud_drm_req_display_mode),
    (GUD_REQ_GET_CONNECTOR_EDID, ctypes.c_uint8 * 128,),
])
@pytest.mark.stall
def test_req_connector_illegal_wValue(gud, req, typ):
    buf = bytearray(ctypes.sizeof(typ))
    num = len(gud.connectors)
    with pytest.raises( (GUDProtocolError, GUDInvalidParameterError) ):
        gud.gud_usb_get(req, num, buf)

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

    #@pytest.mark.skip(reason='timeout: PANIC: ep 0 out was already available')
    # A zero length request is OK
    def test_zero_length(self, gud, req, typ, num, check):
        ret = gud.gud_usb_get(req, 0, None)
        assert len(ret) == 0

    # The device should return the block/struct size
    def test_unaligned_length(self, gud, req, typ, num, check):
        # FORMATS is bytes so won't fail
        if req in (GUD_REQ_GET_FORMATS, ):
            pytest.skip()
        ret = gud.gud_usb_get(req, 0, ctypes.sizeof(typ) + 1)
        assert len(ret) == 0 or len(ret) == ctypes.sizeof(typ)
        if check and len(ret):
            req = typ.from_buffer_copy(ret)
            check([req])

    # Req should fail if length is too short to fill one block/struct
    @pytest.mark.stall
    def test_too_short_length(self, gud, req, typ, num, check):
        # DESCRIPTOR is allowed to return any size
        # FORMATS and STATUS become zero if we subtract one, which is OK
        # EDID is allowed to return zero, the device can cap wLength to save on ctrl req buffer size
        if req in (GUD_REQ_GET_DESCRIPTOR, GUD_REQ_GET_FORMATS, GUD_REQ_GET_CONNECTOR_STATUS, GUD_REQ_GET_CONNECTOR_EDID):
            pytest.skip()
        with pytest.raises(GUDProtocolError):
            gud.gud_usb_get(req, 0, ctypes.sizeof(typ) - 1)

    # Set on a get req should fail
    @pytest.mark.stall
    def test_set_should_fail(self, gud, req, typ, num, check):
        buf = bytearray(ctypes.sizeof(typ))
        with pytest.raises(GUDReqNotSupportedError):
            gud.gud_usb_set(req, 0, buf)


@pytest.mark.parametrize("req,typ", [
    (GUD_REQ_SET_BUFFER, gud_drm_req_set_buffer),
    (GUD_REQ_SET_STATE_CHECK, define_gud_drm_req_set_state(0)),
    (GUD_REQ_SET_STATE_COMMIT, None),
    (GUD_REQ_SET_CONTROLLER_ENABLE, ctypes.c_uint8),
    (GUD_REQ_SET_DISPLAY_ENABLE, ctypes.c_uint8),
])
@pytest.mark.stall
class TestReqSet:
    # Get on a set req should fail
    def test_get_should_fail(self, gud, req, typ):
        with pytest.raises(GUDReqNotSupportedError):
            gud.gud_usb_get(req, 0, 1)

    def test_short_should_fail(self, gud, req, typ):
        if req in (GUD_REQ_SET_STATE_COMMIT, ):
            pytest.skip()
        buf = bytearray(ctypes.sizeof(typ) + 1)
        with pytest.raises(GUDProtocolError):
            gud.gud_usb_set(req, 0, buf)

    def test_long_should_fail(self, gud, req, typ):
        if req in (GUD_REQ_SET_STATE_COMMIT, ):
            buf = bytearray(1)
        else:
            buf = bytearray(ctypes.sizeof(typ) + 1)
        with pytest.raises(GUDProtocolError):
            gud.gud_usb_set(req, 0, buf)
