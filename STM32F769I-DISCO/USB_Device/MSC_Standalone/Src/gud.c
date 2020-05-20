/* SPDX-License-Identifier: CC0-1.0 */

#include <string.h>
#include "drm_fourcc.h"
#include "drm_mode.h"
#include "gud.h"
#include "stm32f769i_discovery_lcd.h"

#define ARRAY_SIZE(x)	sizeof((x)) / sizeof((x)[0])

#define min(x, y)	(x) < (y) ? (x) : (y)


static const uint32_t pixel_formats[] = {
	//DRM_FORMAT_XRGB8888,
	DRM_FORMAT_RGB565,
};

static const uint8_t edid[128] = {
	0x00, 0xff, 0xff, 0xff, 0xff, 0xff , 0xff, 0x00, // Header
	0x04, 0x21, // "AAA"
	0x00, 0x00, // Manufacturer product code. 16-bit number, little-endian.
	0x00, 0x00, 0x00, 0x00, // Serial number. 32 bits, little-endian.
	1, 30, // Manufacture: week, year + 1990
	1, 3, // EDID version 1.3
	0x80, // Digital input: 1, bit depth: undefined, interface: undefined
	0, 0, // width, height in cm
	0, // gamma
	0x0a, // RGB-color, preferred timing in DTD 1
	0, 0, 0, 0, 0, 0, 0, 0, 0, 0, // chroma
	0, 0, 0, // Established timings (not used)
	0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01,  // Standard timing information, filled with unused values
	0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01,  // cont.

	// Detailed Timing Descriptor
	0xb7, 0x0a, // 27429kHz / 10 = 2743=0x0ab7 Pixel clock in 10 kHz units (0.01–655.35 MHz, little-endian).

	0x20, // 800=0x320 Horizontal active pixels 8 lsbits (0–4095)
	16 + 1 + 15, // Horizontal blanking pixels 8 lsbits (0–4095) End of active to start of next active.
	0x30, // Horizontal active pixels 4 msbits << 4 | Horizontal blanking pixels 4 msbits

	0xe0, // 480=0x1e0 Vertical active lines 8 lsbits (0–4095)
	34 + 2 + 34, // Vertical blanking lines 8 lsbits (0–4095)
	0x10, // Vertical active lines 4 msbits << 4 | Vertical blanking lines 4 msbits

	16, // Horizontal front porch (sync offset) pixels 8 lsbits (0–1023) From blanking start
	1, // Horizontal sync pulse width pixels 8 lsbits (0–1023)
	0x22, // 34=0x22 2=0x2  Vertical front porch (sync offset) lines 4 lsbits (0–63) << 4 | Vertical sync pulse width lines 4 lsbits (0–63)
	0x02 << 2, // msbits

	0x00, // Horizontal image size, mm, 8 lsbits (0–4095 mm)
	0x00, // Vertical image size, mm, 8 lsbits (0–4095 mm)
	0x00, // Horizontal image size, mm, 4 msbits << 4 | Vertical image size, mm, 4 msbits

	0x00, // Horizontal border pixels (one side; total is twice this)
	0x00, // Vertical border lines (one side; total is twice this)
	0x00, // Features bitmap

	// Display Range Limits Descriptor
	0x00, 0x00, 0x00,
	0xfd,
	0x00, // Offsets for display range limits
	59, // Minimum vertical field rate (1–255 Hz)
	61, // Maximum vertical field rate (1–255 Hz)
	32, // Minimum horizontal line rate (1–255 kHz)
	33, // Maximum horizontal line rate (1–255 kHz)
	3, // Maximum pixel clock rate, rounded up to 10 MHz multiple (10–2550 MHz).
	0x00, // Extended timing information type: Default GTF
	0xa0, 0x20, 0x20, 0x20, 0x20, 0x20, 0x20, // padding

	// Display name
	0x00, 0x00, 0x00,
	0xfc,
	0x00,
	'S', 'T', 'M', '3', '2', 'F', '7', '6', '9', 'I', '\n', ' ', ' ',

	//// Unspecified text, padding
	//0x00, 0x00, 0x00,
	//0xfe,
	//0x00,
	//'\n', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ',
	// Block 4 unused
	0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,

	0, // Number of extensions to follow. 0 if no extensions.

	0x00, // checksum, filled in later
};

// https://jared.geek.nz/2013/feb/linear-led-pwm
static const uint8_t cie1931[101] = {
	0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 2, 2, 2, 2, 2, 3, 3,
	3, 3, 4, 4, 4, 4, 5, 5, 5, 6, 6, 7, 7, 8, 8, 8, 9, 10, 10, 11,
	11, 12, 12, 13, 14, 15, 15, 16, 17, 18, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27,
	28, 29, 30, 32, 33, 34, 35, 37, 38, 39, 41, 42, 44, 45, 47, 48, 50, 52, 53, 55,
	57, 58, 60, 62, 64, 66, 68, 70, 72, 74, 76, 78, 81, 83, 85, 88, 90, 92, 95, 97, 100
};

static int gud_drm_gadget_check(struct gud_drm_gadget *gdg, struct gud_drm_req_set_state *req,
				size_t size)
{
	unsigned int i;

	gdg->check_ok = 0;

	if (size < sizeof(struct gud_drm_req_set_state))
		return -EINVAL;

	if (size != sizeof(*req) + (sizeof(struct gud_drm_property) * req->num_properties))
		return -EINVAL;

	if (req->mode.hdisplay != gdg->fb.width || req->mode.vdisplay != gdg->fb.height)
		return -EINVAL;

	if (req->connector != 0)
		return -EINVAL;

	switch (req->format) {
	case DRM_FORMAT_RGB565:
	case DRM_FORMAT_XRGB8888:
		break;
	default:
		return -EINVAL;
	}

	for (i = 0; i < req->num_properties; i++) {
		uint16_t prop = req->properties[i].prop;
		uint64_t val = req->properties[i].val;

		switch (prop) {
		case GUD_DRM_PROPERTY_BACKLIGHT_BRIGHTNESS:
			if (val > 100)
				return -EINVAL;
			gdg->brightness = val;
			break;
		//case GUD_DRM_PROPERTY_ROTATION:
		//	ret = drm_client_modeset_set_rotation(client, val);
		//	break;
		default:
			//pr_err("%s: Unknown property: %u\n", __func__, prop);
			continue;
		}

		//if (ret)
		//	return ret;
	}

	gdg->state = *req;
	gdg->check_ok = 1;

	return 0;
}

static int gud_drm_gadget_commit(struct gud_drm_gadget *gdg)
{
	if (!gdg->check_ok)
		return -EINVAL;

	switch (gdg->state.format) {
	case DRM_FORMAT_RGB565:
		gdg->fb.cpp = 2;
		break;
	case DRM_FORMAT_XRGB8888:
		gdg->fb.cpp = 4;
		break;
	default:
		return -EINVAL;
	}

	gdg->fb.pitch = gdg->fb.width * gdg->fb.cpp;

	BSP_LCD_SetBrightness(cie1931[gdg->brightness]);

	return 0;
}

static size_t gud_drm_gadget_write_buffer_memcpy(struct framebuffer *fb,
						 void *dst,
						 const void *src, size_t len,
						 struct gud_drm_req_set_buffer *req)
{
	size_t src_pitch = req->width * fb->cpp;
	size_t dst_pitch = fb->pitch;
	unsigned int y;

	dst += req->y * dst_pitch;
	dst += req->x * fb->cpp;

	for (y = 0; y < req->height && len; y++) {
		src_pitch = min(src_pitch, len);
		memcpy(dst, src, src_pitch);
		src += src_pitch;
		dst += dst_pitch;
		len -= src_pitch;
	}

	return len;
}

int gud_drm_gadget_write_buffer(struct gud_drm_gadget *gdg, void *fb_address, const void *buf, size_t len)
{
	size_t remain;
//	int ret;

//	if (compression & GUD_DRM_COMPRESSION_LZ4) {
//		if (len != gdg->set_buffer_compressed_length) {
//			pr_err("%s: Buffer compressed len differs: %zu != %zu\n",
//			       __func__, len, gdg->set_buffer_compressed_length);
//			return -EINVAL;
//		}
//
//		ret = LZ4_decompress_safe(buf, gdg->work_buf, len, gdg->max_buffer_size);
//		if (ret < 0) {
//			pr_err("%s: Failed to decompress buffer\n", __func__);
//			return -EIO;
//		}
//
//		buf = gdg->work_buf;
//		len = ret;
//	}
//
//	if (len != gdg->set_buffer_length) {
//		pr_err("%s: Buffer len differs: %zu != %zu\n",
//		       __func__, len, gdg->set_buffer_length);
//		return -EINVAL;
//	}
//
//	if (len > (drm_rect_width(rect) * drm_rect_height(rect) * fb->format->cpp[0])) {
//		pr_err("%s: Buffer is too big for rectangle\n", __func__);
//		return -EINVAL;
//	}

	remain = gud_drm_gadget_write_buffer_memcpy(&gdg->fb, fb_address, buf, len, &gdg->req_set_buffer);
	if (remain)
		return -EIO;

	return 0;
}

int gud_drm_gadget_set_buffer(struct gud_drm_gadget *gdg, struct gud_drm_req_set_buffer *req)
{
//	u32 compressed_length = le32_to_cpu(req->compressed_length);
//	u32 length = le32_to_cpu(req->length);
//	int ret = 0;

//	if (size != sizeof(*req))
//		return -EINVAL;

	if (req->x >= gdg->fb.width || req->width > gdg->fb.width ||
	    req->y >= gdg->fb.height || req->height > gdg->fb.height ||
	    req->x + req->width > gdg->fb.width || req->y + req->height > gdg->fb.height)
		return -EINVAL;

//	if (req->compression & ~GUD_DRM_COMPRESSION_LZ4) {
//		ret = -EINVAL;
//		goto out;
//	}

	gdg->req_set_buffer = *req;

//	if (req->compression) {
//		if (!compressed_length) {
//			ret = -EINVAL;
//			goto out;
//		}
//		gdg->set_buffer_compression = req->compression;
//		gdg->set_buffer_compressed_length = compressed_length;
//		length = compressed_length;
//	} else {
//		gdg->set_buffer_compression = 0;
//		gdg->set_buffer_compressed_length = 0;
//	}
//out:
//	return ret ? ret : length;

	return req->length;
}

int gud_drm_gadget_disable_pipe(struct gud_drm_gadget *gdg)
{
//	int ret;
//
//	ret = drm_client_modeset_disable(&gdg->client);
//	gud_drm_gadget_delete_buffers(gdg);
//
//	return ret;
	return 0;
}

static int gud_drm_gadget_ctrl_get_display_descriptor(struct gud_drm_gadget *gdg, uint16_t value,
						      void *data, size_t size)
{
	uint32_t max_buffer_size = gdg->max_buffer_size;
	struct gud_drm_display_descriptor desc;
	uint8_t type = value >> 8;
	uint8_t index = value & 0xff;
	uint32_t lg = 0;

	if (type != GUD_DRM_USB_DT_DISPLAY || index)
		return -EINVAL;

	desc.bLength = sizeof(desc);
	desc.bDescriptorType = GUD_DRM_USB_DT_DISPLAY;

	desc.bVersion = 1;

	while (max_buffer_size >>= 1)
		lg++;

	// If the buffer size is not power of two, assume it's big enough and round up to tell the host we can handle full frames
	if ((1 << lg) < gdg->max_buffer_size)
		desc.bMaxBufferSizeOrder = lg + 1;
	else
		desc.bMaxBufferSizeOrder = lg;

	desc.bmFlags = 0;
	desc.bCompression = 0; //GUD_DRM_COMPRESSION_LZ4;

	desc.dwMinWidth = gdg->fb.width;
	desc.dwMaxWidth = gdg->fb.width;
	desc.dwMinHeight = gdg->fb.height;
	desc.dwMaxHeight = gdg->fb.height;
	desc.bNumFormats = ARRAY_SIZE(pixel_formats);
	desc.bNumProperties = 0;
	desc.bNumConnectors = 1;

	size = size < sizeof(desc) ? size : sizeof(desc);
	memcpy(data, &desc, size);

	return size;
}

static int gud_drm_gadget_ctrl_get_formats(struct gud_drm_gadget *gdg, uint32_t *formats, uint16_t size)
{
	unsigned int i;

	if (size != sizeof(pixel_formats))
		return -EINVAL;

	for (i = 0; i < ARRAY_SIZE(pixel_formats); i++)
		formats[i] = pixel_formats[i];

	return 0;
}

static int gud_drm_gadget_ctrl_get_connector(struct gud_drm_gadget *gdg, unsigned int index,
					     struct gud_drm_req_get_connector *desc)
{
	if (index != 0)
		return -EINVAL;

	memset(desc, 0, sizeof(*desc));

	desc->connector_type = DRM_MODE_CONNECTOR_DSI;
	desc->flags = 0;
	desc->num_properties = 1;

	return 0;
}

static int gud_drm_gadget_ctrl_get_connector_status(struct gud_drm_gadget *gdg, unsigned int index,
						    struct gud_drm_req_get_connector_status *status)
{
	if (index)
		return -EINVAL;

	memset(status, 0, sizeof(*status));

	status->status = 1; // connector_status_connected
	status->num_modes = 0;
	status->edid_len = sizeof(edid);

	return 0;
}

static int gud_drm_gadget_ctrl_get_connector_edid(struct gud_drm_gadget *gdg, unsigned int index,
						  uint8_t *data, uint16_t len)
{
	uint8_t checksum = 0;
	unsigned int i;

	if (index || len != sizeof(edid))
		return -EINVAL;

	memcpy(data, edid, len);

	for (i = 0; i < len; i++)
		checksum += edid[i];

	data[127] = 0xff - checksum + 1;

	return 0;
}

int gud_drm_gadget_ctrl_get(struct gud_drm_gadget *gdg, uint8_t request,
			    uint16_t index, void *data, uint16_t size)
{
	struct gud_drm_property *prop;
	int ret = -EINVAL;

	if (!size)
		return -EINVAL;

	switch (request) {
	case 0x06: // USB_REQ_GET_DESCRIPTOR:
		ret = gud_drm_gadget_ctrl_get_display_descriptor(gdg, index, data, size);
		break;
	case GUD_DRM_USB_REQ_GET_FORMATS:
		if (!index)
			ret = gud_drm_gadget_ctrl_get_formats(gdg, data, size);
		break;
	case GUD_DRM_USB_REQ_GET_PROPERTIES:
		//if (!index && size == gdg->num_properties * sizeof(*gdg->properties)) {
		//	memcpy(data, gdg->properties, size);
		//	ret = 0;
		//}
		break;
	case GUD_DRM_USB_REQ_GET_CONNECTOR:
		if (size == sizeof(struct gud_drm_req_get_connector))
			ret = gud_drm_gadget_ctrl_get_connector(gdg, index, data);
		break;
	case GUD_DRM_USB_REQ_GET_CONNECTOR_PROPERTIES:
		if (index == 0 && size == sizeof(*prop)) {
			prop = data;
			prop->prop = GUD_DRM_PROPERTY_BACKLIGHT_BRIGHTNESS;
			prop->val = gdg->brightness;
			ret = 0;
		}
		break;
	case GUD_DRM_USB_REQ_GET_CONNECTOR_STATUS:
		if (size == sizeof(struct gud_drm_req_get_connector_status))
			ret = gud_drm_gadget_ctrl_get_connector_status(gdg, index, data);
		break;
	case GUD_DRM_USB_REQ_GET_CONNECTOR_MODES:
		break;
	case GUD_DRM_USB_REQ_GET_CONNECTOR_EDID:
		ret = gud_drm_gadget_ctrl_get_connector_edid(gdg, index, data, size);
		break;
	}

	gdg->errno = -ret;

	return !ret ? size : ret;
}

int gud_drm_gadget_ctrl_set(struct gud_drm_gadget *gdg, uint8_t request,
			    uint16_t index, void *data, uint16_t size)
{
	int ret = -EINVAL;

	switch (request) {
	case GUD_DRM_USB_REQ_SET_CONNECTOR_FORCE_DETECT:
		ret = 0;
		break;
	case GUD_DRM_USB_REQ_SET_STATE_CHECK:
		ret = gud_drm_gadget_check(gdg, data, size);
		break;
	case GUD_DRM_USB_REQ_SET_STATE_COMMIT:
		if (!size)
			ret = gud_drm_gadget_commit(gdg);
		break;
	case GUD_DRM_USB_REQ_SET_CONTROLLER_ENABLE:
		if (size == sizeof(uint8_t)) {
			if (*(uint8_t *)data == 0)
				//ret = gud_drm_gadget_disable_pipe(gdg);
				ret = 0;
			else
				ret = 0;
		}
		break;
	case GUD_DRM_USB_REQ_SET_DISPLAY_ENABLE:
		if (size == sizeof(uint8_t)) {
			if (*(uint8_t *)data)
				BSP_LCD_DisplayOn();
			else
				BSP_LCD_DisplayOff();
			ret = 0;
		}
		break;
	}

	gdg->errno = -ret;

	return ret;
}

void gud_drm_gadget_init(struct gud_drm_gadget *gdg, uint32_t width, uint32_t height, size_t len)
{
	gdg->fb.width = width;
	gdg->fb.height = height;
	gdg->brightness = 100;
	gdg->max_buffer_size = len;
}
