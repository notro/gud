// SPDX-License-Identifier: CC0-1.0

#include "tusb_option.h"

#include "driver.h"
#include "device/usbd_pvt.h"

#include "gud.h"
#include "lz4.h"

#define GUD_DRV_LOG1
#define GUD_DRV_LOG2

#define GUD_CTRL_REQ_BUF_SIZE   128 // Fits EDID
// Max usbd_edpt_xfer() xfer size is uint16_t, align to endpoint size
#define GUD_EDPT_XFER_MAX_SIZE  (0xffff - (0xffff % CFG_GUD_BULK_OUT_SIZE))

#define min(a,b)    (((a) < (b)) ? (a) : (b))

typedef struct
{
    uint8_t itf_num;
    uint8_t ep_out;

    uint8_t *buf;
    uint32_t xfer_len;
    uint32_t len;
    uint32_t offset;
} gud_interface_t;

CFG_TUSB_MEM_SECTION static gud_interface_t _gud_itf;

const struct gud_display *_display;
uint8_t *_framebuffer;
uint8_t *_compress_buf;

CFG_TUSB_MEM_SECTION CFG_TUSB_MEM_ALIGN static uint8_t _ctrl_req_buf[GUD_CTRL_REQ_BUF_SIZE];
CFG_TUSB_MEM_SECTION CFG_TUSB_MEM_ALIGN static uint8_t status;

static void gud_driver_init(void)
{
    tu_memclr(&_gud_itf, sizeof(_gud_itf));
}

static void gud_driver_reset(uint8_t rhport)
{
    (void) rhport;

//    tu_memclr(&_gud_itf, ITF_MEM_RESET_SIZE);
}

static uint16_t gud_driver_open(uint8_t rhport, tusb_desc_interface_t const * itf_desc, uint16_t max_len)
{
    GUD_DRV_LOG1("%s:\n", __func__);

    TU_VERIFY(TUSB_CLASS_VENDOR_SPECIFIC == itf_desc->bInterfaceClass, 0);

    uint16_t const drv_len = sizeof(tusb_desc_interface_t) + itf_desc->bNumEndpoints*sizeof(tusb_desc_endpoint_t);
    TU_VERIFY(max_len >= drv_len, 0);

    tusb_desc_endpoint_t const * desc_ep = (tusb_desc_endpoint_t const *) tu_desc_next(itf_desc);
    TU_ASSERT(usbd_edpt_open(rhport, desc_ep), 0);
    _gud_itf.ep_out = desc_ep->bEndpointAddress;
    _gud_itf.itf_num = itf_desc->bInterfaceNumber;

    return drv_len;
}

static bool gud_driver_control_request(uint8_t rhport, tusb_control_request_t const * req)
{
    uint16_t wLength;
    int ret;

    wLength = min(req->wLength, sizeof(_ctrl_req_buf));

    GUD_DRV_LOG2("%s:  bRequest=0x%02x bmRequestType=0x%x %s wLength=%u(%u) \n",
                 __func__, req->bRequest, req->bmRequestType,
                 req->bmRequestType_bit.direction ? "IN" : "OUT", wLength, req->wLength);

//    } else if (req_type == USB_TYPE_VENDOR && req_recipient == USB_RECIPIENT_INTERFACE) {

    if (req->bmRequestType_bit.direction) {

        if (req->bRequest == GUD_REQ_GET_STATUS) {
            GUD_DRV_LOG2("GUD_REQ_GET_STATUS=%u\n", status);
            return tud_control_xfer(rhport, req, &status, sizeof(status));
        }

        status = 0;
        ret = gud_req_get(_display, req->bRequest, req->wValue, _ctrl_req_buf, wLength);
        if (ret < 0) {
            status = -ret;
            return false;
        }

        return tud_control_xfer(rhport, req, _ctrl_req_buf, ret);
    } else {
        status = 0;

        if (!wLength) {
            int ret = gud_req_set(_display, req->bRequest, req->wValue, _ctrl_req_buf, 0);
            if (ret < 0) {
                status = -ret;
                return false;
            }
        }

        return tud_control_xfer(rhport, req, _ctrl_req_buf, wLength);
    }

    return false;
}

static bool gud_driver_bulk_xfer(uint8_t rhport, uint8_t *buf, uint32_t xfer_len, uint32_t len)
{
    TU_ASSERT(!usbd_edpt_busy(rhport, _gud_itf.ep_out));

    if (buf) {
        TU_ASSERT(xfer_len && len);
        _gud_itf.offset = 0;
        _gud_itf.buf = buf;
        _gud_itf.len = len;
        _gud_itf.xfer_len = xfer_len;
    } else {
        _gud_itf.offset += GUD_EDPT_XFER_MAX_SIZE;
        buf = _gud_itf.buf + _gud_itf.offset;
        xfer_len = _gud_itf.xfer_len - _gud_itf.offset;
    }

    if (xfer_len > GUD_EDPT_XFER_MAX_SIZE)
        xfer_len = GUD_EDPT_XFER_MAX_SIZE;

    return usbd_edpt_xfer(rhport, _gud_itf.ep_out, buf, xfer_len);
}

static bool gud_driver_control_complete(uint8_t rhport, tusb_control_request_t const * req)
{
    uint16_t wLength;

    wLength = min(req->wLength, sizeof(_ctrl_req_buf));

    GUD_DRV_LOG2("%s: bRequest=0x%02x bmRequestType=0x%x %s wLength=%u(%u)\n",
                 __func__, req->bRequest, req->bmRequestType,
                 req->bmRequestType_bit.direction ? "IN" : "OUT", wLength, req->wLength);

    if (!req->bmRequestType_bit.direction) {
        int ret = gud_req_set(_display, req->bRequest, req->wValue, _ctrl_req_buf, wLength);
        if (ret < 0) {
            status = -ret;
            return false;
        }

        if (req->bRequest == GUD_REQ_SET_BUFFER) {
            const struct gud_set_buffer_req *buf_req = (const struct gud_set_buffer_req *)_ctrl_req_buf;
            uint32_t len;
            void *buf;

            if (buf_req->compression) {
                buf = _compress_buf;
                len = buf_req->compressed_length;
            } else {
                buf = _framebuffer;
                len = buf_req->length;
            }

            return gud_driver_bulk_xfer(rhport, buf, len, buf_req->length);
        }

        if (req->bRequest == GUD_REQ_SET_STATE_CHECK && _display->flags & GUD_DISPLAY_FLAG_FULL_UPDATE) {
            if (!usbd_edpt_busy(rhport, _gud_itf.ep_out)) {
                const struct gud_state_req *req = (const struct gud_state_req *)_ctrl_req_buf;

                uint32_t len = gud_get_buffer_length(req->format, _display->width, _display->height);
                if (!len) {
                    status = GUD_STATUS_INVALID_PARAMETER;
                    return false;
                }

                return gud_driver_bulk_xfer(rhport, _framebuffer, len, len);
            }
        }
    }

    return true;
}

static bool gud_driver_xfer_cb(uint8_t rhport, uint8_t ep_addr, xfer_result_t result, uint32_t xferred_bytes)
{
    TU_VERIFY(result == XFER_RESULT_SUCCESS);

    if (xferred_bytes != (_gud_itf.xfer_len - _gud_itf.offset)) {
        if (xferred_bytes != GUD_EDPT_XFER_MAX_SIZE) {
            GUD_DRV_LOG1("%s: UNHANDLED: xferred_bytes=%u != _gud_itf.xfer_len=%u\n",
                         __func__, xferred_bytes, _gud_itf.xfer_len);
            return false;
        }
        return gud_driver_bulk_xfer(rhport, NULL, 0, 0);
    }

    if (_gud_itf.xfer_len != _gud_itf.len) {
        //uint64_t start = time_us_64();

        int ret = LZ4_decompress_safe(_gud_itf.buf, _framebuffer, _gud_itf.xfer_len, _gud_itf.len);
        if (ret < 0) {
            GUD_DRV_LOG1("LZ4_decompress_safe failed: xfer_len=%u len=%u\n", _gud_itf.xfer_len, _gud_itf.len);
            return false;
        }

        //printf("%llu\n", time_us_64() - start);
    }

    gud_write_buffer(_display, _framebuffer);

    if (_display->flags & GUD_DISPLAY_FLAG_FULL_UPDATE)
        return gud_driver_bulk_xfer(rhport, _framebuffer, _gud_itf.xfer_len, _gud_itf.xfer_len);

    return true;
}

static usbd_class_driver_t const _usbd_driver[] =
{
    {
  #if CFG_TUSB_DEBUG >= 2
        .name             = "GUD",
  #endif
        .init             = gud_driver_init,
        .reset            = gud_driver_reset,
        .open             = gud_driver_open,
        .control_request  = gud_driver_control_request,
        .control_complete = gud_driver_control_complete,
        .xfer_cb          = gud_driver_xfer_cb,
        .sof              = NULL
    },
};

usbd_class_driver_t const* usbd_app_driver_get_cb(uint8_t* driver_count)
{
	*driver_count += TU_ARRAY_SIZE(_usbd_driver);

	return _usbd_driver;
}

void gud_driver_setup(const struct gud_display *disp, void *framebuffer, void *compress_buf)
{
    if (disp->compression && !compress_buf)
        panic("Missing compress_buf");

    _display = disp;
    _framebuffer = framebuffer;
    _compress_buf = compress_buf;
}
