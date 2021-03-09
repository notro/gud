/*
 * SPDX-License-Identifier: MIT
 */

#include <stdio.h>
#include <string.h>

#include "gud.h"

#define GUD_LOG1
#define GUD_LOG2

#define min(a,b)	(((a) < (b)) ? (a) : (b))

#define div_round_up(n,d)	(((n) + (d) - 1) / (d))

struct gud_set_buffer_req _set_buf;

#define GUD_MAX_PROPERTIES 8

// struct with room for properties, since no malloc.
struct gud_state_req_with_property_array {
	struct gud_display_mode_req mode;
	uint8_t format;
	uint8_t connector;
	struct gud_property_req properties[GUD_MAX_PROPERTIES];
} __attribute__((packed));

static struct gud_state_req_with_property_array _state;
static uint8_t _state_num_properties;

static int gud_req_get_descriptor(const struct gud_display *disp, void *data, size_t size)
{
	struct gud_display_descriptor_req desc;

	// If ever a setup/init function arises, move this check:
	if ((disp->num_properties + disp->num_connector_properties) > GUD_MAX_PROPERTIES)
		return -GUD_STATUS_ERROR;

	if (!size)
		return -GUD_STATUS_PROTOCOL_ERROR;

	desc.magic = GUD_DISPLAY_MAGIC;
	desc.version = 1;
	desc.max_buffer_size = 0;
	desc.flags = disp->flags;
	desc.compression = disp->compression;

	desc.min_width = disp->width;
	desc.max_width = disp->width;
	desc.min_height = disp->height;
	desc.max_height = disp->height;

	size = min(size, sizeof(desc));
	memcpy(data, &desc, size);

	return size;
}

static int gud_req_get_formats(const struct gud_display *disp, void *data, size_t size)
{
	size = min(size, disp->num_formats);
	memcpy(data, disp->formats, size);

	return size;
}

static int gud_req_get_properties(const struct gud_display *disp,
				  void *data, size_t size)
{
	size = size - (size % sizeof(*disp->properties));
	if (!size)
		return -GUD_STATUS_PROTOCOL_ERROR;

	size = min(size, disp->num_properties * sizeof(*disp->properties));
	memcpy(data, disp->properties, size);

	return size;
}

static int gud_req_get_connectors(const struct gud_display *disp, struct gud_connector_descriptor_req *desc, size_t size)
{
	if (size < sizeof(*desc))
		return -GUD_STATUS_PROTOCOL_ERROR;

	desc->connector_type = GUD_CONNECTOR_TYPE_PANEL;
	desc->flags = 0;

	return sizeof(*desc);
}

static int gud_req_get_connector_properties(const struct gud_display *disp,
					    void *data, size_t size)
{
	size = size - (size % sizeof(*disp->connector_properties));
	if (!size)
		return -GUD_STATUS_PROTOCOL_ERROR;

	size = min(size, disp->num_connector_properties * sizeof(*disp->connector_properties));
	memcpy(data, disp->connector_properties, size);

	return size;
}

static int gud_req_get_connector_status(const struct gud_display *disp, uint8_t *status, size_t size)
{
	if (!size)
		return -GUD_STATUS_PROTOCOL_ERROR;

	*status = GUD_CONNECTOR_STATUS_CONNECTED;

	return sizeof(*status);
}

static int gud_req_get_connector_modes(const struct gud_display *disp, struct gud_display_mode_req *mode, size_t size)
{
//	if (disp->edid)
//		return 0;

	if (size < sizeof(*mode))
		return -GUD_STATUS_PROTOCOL_ERROR;

	mode->clock = 1;
	mode->hdisplay = disp->width;
	mode->hsync_start = mode->hdisplay;
	mode->hsync_end = mode->hdisplay;
	mode->htotal = mode->hdisplay;
	mode->vdisplay = disp->height;
	mode->vsync_start = mode->vdisplay;
	mode->vsync_end = mode->vdisplay;
	mode->vtotal = mode->vdisplay;
	mode->flags = 0;

	return sizeof(*mode);
}

static int gud_req_get_connector_edid(const struct gud_display *disp,
				      uint8_t *edid, size_t size)
{
	// Caller might cap wLength to save on buffer size so don't return an error
	if (size < 128)
		return 0;

	if (!disp->edid ||
	    !disp->edid->name || strlen(disp->edid->name) > 13 ||
	    !disp->edid->pnp || strlen(disp->edid->pnp) != 3)
		return 0;

	// Header
	edid[0] = 0x00; edid[1] = 0xff; edid[2] = 0xff; edid[3] = 0xff;
	edid[4] = 0xff; edid[5] = 0xff; edid[6] = 0xff; edid[7] = 0x00;

	// Plug'n Play Id
	uint8_t pnp[3];
	for (uint8_t i = 0; i < 3; i++)
		pnp[i] = disp->edid->pnp[i] - 'A' + 1;
	edid[8] = pnp[0] << 2 | pnp[1] >> 3;
	edid[9] = pnp[1] << 5 | pnp[2];

	// Manufacturer product code. 16 bits, little-endian.
	edid[10] = disp->edid->product_code;
	edid[11] = disp->edid->product_code >> 8;

	// Serial number. 32 bits, little-endian.
	uint32_t serial = 0;
	if (disp->edid->get_serial_number)
		serial = disp->edid->get_serial_number();
	for (uint8_t i = 12; i < 16; i++) {
		edid[i] = serial & 0xff;
		serial >>= 8;
	}

	// Manufacture
	edid[16] = 1; // week
	if (disp->edid->year > 1990)
		edid[17] = disp->edid->year - 1990;
	else
		edid[17] = 0;

	// EDID version 1.3
	edid[18] = 1; edid[19] = 3;

	// Basic display parameters
	edid[20] = 0x80;  // Digital input: 1, bit depth: undefined, interface: undefined
	edid[21] = div_round_up(disp->edid->width_mm, 10); // width in cm
	edid[22] = div_round_up(disp->edid->height_mm, 10); // height in cm
	edid[23] = 0; // gamma
	edid[24] = 0x0a; // RGB-color, preferred timing in DTD 1

	// chroma
	memset(edid + 25, 0, 10);

	// Established timings (not used)
	memset(edid + 35, 0, 3);

	// Standard timing information, filled with unused values
	memset(edid + 38, 0x01, 16);

	// Descriptor 1 (54-71): Detailed Timing Descriptor
	uint32_t framerate = 60;
	uint32_t clock_khz = disp->width * disp->height * framerate / 1000;
	// Pixel clock in 10 kHz units (0.01–655.35 MHz, little-endian).
	edid[54] = div_round_up(clock_khz, 10); edid[55] = div_round_up(clock_khz, 10) >> 8;

	edid[56] = disp->width & 0xff; // Horizontal active pixels 8 lsbits (0–4095)
	edid[57] = 0x00; // Horizontal blanking pixels 8 lsbits (0–4095) End of active to start of next active.
	edid[58] = (disp->width >> 8) << 4; // Horizontal active pixels 4 msbits << 4 | Horizontal blanking pixels 4 msbits

	edid[59] = disp->height & 0xff; // 480=0x1e0 Vertical active lines 8 lsbits (0–4095)
	edid[60] = 0x00; // Vertical blanking lines 8 lsbits (0–4095)
	edid[61] = (disp->height >> 8) << 4; // Vertical active lines 4 msbits << 4 | Vertical blanking lines 4 msbits

	edid[62] = 0x00; // Horizontal front porch (sync offset) pixels 8 lsbits (0–1023) From blanking start
	// DRM chokes on zero pulse width, so use 1:
	edid[63] = 0x01; // Horizontal sync pulse width pixels 8 lsbits (0–1023)
	edid[64] = 0x01; // Vertical front porch (sync offset) lines 4 lsbits (0–63) << 4 | Vertical sync pulse width lines 4 lsbits (0–63)
	edid[65] = 0x00; // msbits

	edid[66] = disp->edid->width_mm & 0xff; // Horizontal image size, mm, 8 lsbits (0–4095 mm)
	edid[67] = disp->edid->height_mm & 0xff; // Vertical image size, mm, 8 lsbits (0–4095 mm)
	edid[68] = (disp->edid->width_mm >> 8) << 4 |
		   disp->edid->height_mm >> 8; // Horizontal image size, mm, 4 msbits << 4 | Vertical image size, mm, 4 msbits

	edid[69] = 0x00; // Horizontal border pixels (one side; total is twice this)
	edid[70] = 0x00; // Vertical border lines (one side; total is twice this)
	edid[71] = 0x1e; // Features bitmap: Non-Interlaced, Normal Display – No Stereo, Digital Separate Sync, +vsync, +hsync

	// Descriptor 2 (72-89): Display name
	edid[72] = 0x00; edid[73] = 0x00; edid[74] = 0x00;
	edid[75] = 0xfc;
	edid[76] = 0x00;
	memset(edid + 77, 0x20, 13); // unused: pad with spaces
	uint8_t name_len = strlen(disp->edid->name);
	memcpy(edid + 77, disp->edid->name, name_len);
	if (name_len < 13)
		edid[77 + name_len] = 0x0a; // terminate short string with line feed

	// Descriptor 3 (90-107): Unused
	memset(edid + 90, 0, 18);

	// Descriptor 4 (108-125): Unused
	memset(edid + 108, 0, 18);

	// Number of extensions to follow. 0 if no extensions.
	edid[126] = 0;

	// checksum
	uint8_t checksum = 0;
	for (uint8_t i = 0; i < 127; i++)
		checksum += edid[i];
	edid[127] = 0xff - checksum + 1;

	return 128;
}

int gud_req_get(const struct gud_display *disp, uint8_t request, uint16_t index, void *data, size_t size)
{
	int ret;

	GUD_LOG2("%s: request=0x%x index=%u size=%zu\n", __func__, request, index, size);

	if (index)
		return -GUD_STATUS_PROTOCOL_ERROR;

	switch (request) {
	case GUD_REQ_GET_DESCRIPTOR:
		ret = gud_req_get_descriptor(disp, data, size);
		break;
	case GUD_REQ_GET_FORMATS:
		ret = gud_req_get_formats(disp, data, size);
		break;
	case GUD_REQ_GET_PROPERTIES:
		ret = gud_req_get_properties(disp, data, size);
		break;
	case GUD_REQ_GET_CONNECTORS:
		ret = gud_req_get_connectors(disp, data, size);
		break;
	case GUD_REQ_GET_CONNECTOR_PROPERTIES:
		ret = gud_req_get_connector_properties(disp, data, size);
		break;
//	case GUD_REQ_GET_CONNECTOR_TV_MODE_VALUES:
//		ret = gud_req_get_connector_tv_mode_values(disp, data, size);
//		break;
	case GUD_REQ_GET_CONNECTOR_STATUS:
		ret = gud_req_get_connector_status(disp, data, size);
		break;
	case GUD_REQ_GET_CONNECTOR_MODES:
		ret = gud_req_get_connector_modes(disp, data, size);
		break;
	case GUD_REQ_GET_CONNECTOR_EDID:
		ret = gud_req_get_connector_edid(disp, data, size);
		break;
	default:
		ret = -GUD_STATUS_REQUEST_NOT_SUPPORTED;
		break;
	}

	return ret;
}

uint32_t gud_get_buffer_length(uint8_t format, uint32_t width, uint32_t height)
{
    if (!width || !height)
        return 0;

    switch (format) {
    case GUD_PIXEL_FORMAT_R1:
        return div_round_up(width, 8) * height;
    case GUD_PIXEL_FORMAT_RGB111:
        return div_round_up(width, 2) * height;
    case GUD_PIXEL_FORMAT_RGB565:
        return width * height * 2;
    case GUD_PIXEL_FORMAT_XRGB8888:
    case GUD_PIXEL_FORMAT_ARGB8888:
        return width * height * 4;
    }

    return 0;
}

static int gud_req_set_buffer(const struct gud_display *disp, const struct gud_set_buffer_req *req, size_t size)
{
	size_t length;
	int ret;

	if (size != sizeof(*req))
		return -GUD_STATUS_PROTOCOL_ERROR;

	GUD_LOG1("%s: x=%u y=%u width=%u height=%u length=%u compression=0x%x compressed_length=%u\n",
		 __func__, req->x, req->y, req->width, req->height, req->length,
		 req->compression, req->compressed_length);

	if (req->x >= disp->width || req->y >= disp->height ||
	    (req->x + req->width) > disp->width || (req->y + req->height) > disp->height)
		return -GUD_STATUS_INVALID_PARAMETER;

	if (req->compression && !req->compressed_length)
		return -GUD_STATUS_INVALID_PARAMETER;

	switch (_state.format) {
	case GUD_PIXEL_FORMAT_R1:
		length = req->width * req->height / 8;
		break;
	case GUD_PIXEL_FORMAT_RGB565:
		length = req->width * req->height * 2;
		break;
	case GUD_PIXEL_FORMAT_XRGB8888:
	case GUD_PIXEL_FORMAT_ARGB8888:
		length = req->width * req->height * 4;
		break;
	default:
		return -GUD_STATUS_INVALID_PARAMETER;
	}

	if (req->length != length)
		return -GUD_STATUS_INVALID_PARAMETER;

	if (disp->set_buffer)
		ret = disp->set_buffer(disp, req);
	else
		ret = 0;

	_set_buf = *req;

	return ret;
}

static int gud_req_set_state_check(const struct gud_display *disp, const struct gud_state_req *req, size_t size)
{
	unsigned int i, num_properties;

	GUD_LOG1("%s: mode=%ux%u format=0x%02x connector=%u\n",
		 __func__, req->mode.hdisplay, req->mode.vdisplay, req->format, req->connector);

	if (size < sizeof(*req))
		return -GUD_STATUS_PROTOCOL_ERROR;

	if ((size - sizeof(*req)) % sizeof(*req->properties))
		return -GUD_STATUS_PROTOCOL_ERROR;

	num_properties = (size - sizeof(*req)) / sizeof(*req->properties);
	if (num_properties > disp->num_properties + disp->num_connector_properties)
		return -GUD_STATUS_PROTOCOL_ERROR;

	if (req->mode.hdisplay != disp->width || req->mode.vdisplay != disp->height ||
	    req->connector != 0)
		return -GUD_STATUS_INVALID_PARAMETER;

	for (i = 0; i < disp->num_formats; i++) {
		if (req->format == disp->formats[i])
			break;
	}
	if (i == disp->num_formats)
		return -GUD_STATUS_INVALID_PARAMETER;

	memcpy(&_state, req, size);
	_state_num_properties = num_properties;

    if (disp->flags & GUD_DISPLAY_FLAG_FULL_UPDATE) {
        _set_buf.x = 0;
        _set_buf.y = 0;
        _set_buf.width = disp->width;
        _set_buf.height = disp->height;
        _set_buf.length = gud_get_buffer_length(req->format, disp->width, disp->height);
        _set_buf.compression = 0;
        _set_buf.compressed_length = 0;
    }

	return 0;
}

static int gud_req_set_state_commit(const struct gud_display *disp, size_t size)
{
	int ret;

	GUD_LOG1("%s:\n", __func__);

	if (disp->state_commit)
		ret = disp->state_commit(disp, (const struct gud_state_req *)&_state, _state_num_properties);
	else
		ret = 0;

	return ret;
}

static int gud_req_set_controller_enable(const struct gud_display *disp, const uint8_t *enable, size_t size)
{
	int ret;

	if (size != sizeof(*enable))
		return -GUD_STATUS_REQUEST_NOT_SUPPORTED;

	GUD_LOG1("%s: enable=%u\n", __func__, *enable);

	if (disp->controller_enable)
		ret = disp->controller_enable(disp, *enable);
	else
		ret = 0;

	return ret;
}

static int gud_req_set_display_enable(const struct gud_display *disp, const uint8_t *enable, size_t size)
{
	int ret;

	if (size != sizeof(*enable))
		return -GUD_STATUS_REQUEST_NOT_SUPPORTED;

	GUD_LOG1("%s: enable=%u\n", __func__, *enable);

	if (disp->display_enable)
		ret = disp->display_enable(disp, *enable);
	else
		ret = 0;

	return ret;
}

int gud_req_set(const struct gud_display *disp, uint8_t request, uint16_t index, const void *data, size_t size)
{
	int ret;

	GUD_LOG2("%s: request=0x%x index=%u size=%zu\n", __func__, request, index, size);

	if (index)
		return -GUD_STATUS_PROTOCOL_ERROR;

	switch (request) {
	case GUD_REQ_SET_CONNECTOR_FORCE_DETECT:
		ret = 0;
		break;
	case GUD_REQ_SET_BUFFER:
		ret = gud_req_set_buffer(disp, data, size);
		break;
	case GUD_REQ_SET_STATE_CHECK:
		ret = gud_req_set_state_check(disp, data, size);
		break;
	case GUD_REQ_SET_STATE_COMMIT:
		ret = gud_req_set_state_commit(disp, size);
		break;
	case GUD_REQ_SET_CONTROLLER_ENABLE:
		ret = gud_req_set_controller_enable(disp, data, size);
		break;
	case GUD_REQ_SET_DISPLAY_ENABLE:
		ret = gud_req_set_display_enable(disp, data, size);
		break;
	default:
		ret = -GUD_STATUS_REQUEST_NOT_SUPPORTED;
		break;
	}

	return ret;
}

void gud_write_buffer(const struct gud_display *disp, void *buf)
{
	if (disp->write_buffer)
		disp->write_buffer(disp, &_set_buf, buf);
}
