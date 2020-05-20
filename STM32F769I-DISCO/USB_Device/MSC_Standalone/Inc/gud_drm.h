/* SPDX-License-Identifier: MIT */
/*
 * Copyright 2020 Noralf Trønnes
 */

#ifndef __LINUX_GUD_DRM_H
#define __LINUX_GUD_DRM_H

//#include <drm/drm_modes.h>
//#include <linux/types.h>
//#include <uapi/drm/drm_fourcc.h>
//#include <uapi/linux/usb/ch9.h>

#include "drm.h"






/*
 * Maximum size of a control message, fits 120 display modes.
 * If this needs to increase, the IN side in f_gud_drm_setup()
 * needs fixing.
 */
//#define GUD_DRM_MAX_TRANSFER_SIZE	SZ_4K
// edid is the biggest when there's only one display mode
#define GUD_DRM_MAX_TRANSFER_SIZE	512


#define GUD_DRM_USB_DT_DISPLAY		(USB_TYPE_VENDOR | 0x4)

/*
 * struct gud_drm_display_descriptor - Display descriptor
 * @bLength: Size of descriptor in bytes
 * @bDescriptorType: DescriptorType (GUD_DRM_USB_DT_DISPLAY)
 * @bVersion: Protocol version
 * @bMaxBufferSizeOrder: Maximum buffer size the device can handle as log2
 * @bmFlags: Currently unused, should be set to zero
 * @bCompression: Supported compression types
 * @dwMinWidth: Minimum pixel width the controller can handle
 * @dwMaxWidth: Maximum width
 * @dwMinHeight: Minimum height
 * @dwMaxHeight: Maximum height
 * @bNumFormats: Number of supported pixel formats
 * @bNumProperties: Number of properties that are not connector porperties
 * @bNumConnectors: Number of connectors
 *
 * Devices that have only one display mode will have dwMinWidth == dwMaxWidth
 * and dwMinHeight == dwMaxHeight.
 *
 */
struct gud_drm_display_descriptor {
	__u8 bLength;
	__u8 bDescriptorType;

	__u8 bVersion;
	__u8 bMaxBufferSizeOrder;
	__le32 bmFlags;

	__u8 bCompression;
#define GUD_DRM_COMPRESSION_LZ4		BIT(0)

	__le32 dwMinWidth;
	__le32 dwMaxWidth;
	__le32 dwMinHeight;
	__le32 dwMaxHeight;

	__u8 bNumFormats;
	__u8 bNumProperties;
	__u8 bNumConnectors;
} __packed;

/*
 * struct gud_drm_req_get_status - Status request
 * @flags: Flags
 * @errno: Linux errno value
 *
 * The host keeps polling for status as long as the GUD_DRM_STATUS_PENDING flag
 * is set (or until timeout). Requested using: USB_REQ_GET_STATUS.
 */
struct gud_drm_req_get_status {
	__u8 flags;
#define GUD_DRM_STATUS_PENDING	BIT(0)
	__u8 errno;
} __packed;

/*
 * struct gud_drm_property - Property
 * @prop: Property
 * @val: Value
 */
struct gud_drm_property {
	__le16 prop;
	__le64 val;
} __packed;

/* See &drm_display_mode for the meaning of these fields */
struct gud_drm_display_mode {
	__le32 clock;
	__le16 hdisplay;
	__le16 hsync_start;
	__le16 hsync_end;
	__le16 htotal;
	__le16 hskew;
	__le16 vdisplay;
	__le16 vsync_start;
	__le16 vsync_end;
	__le16 vtotal;
	__le16 vscan;
	__le32 vrefresh;
	__le32 flags;
	__u8 type;
} __packed;

/*
 * struct gud_drm_req_get_connector - Connector descriptor
 * @connector_type: Connector type (DRM_MODE_CONNECTOR_*)
 * @flags: Flags
 * @num_properties: Number of supported properties
 */
struct gud_drm_req_get_connector {
	__u8 connector_type;

	__le32 flags;
#define GUD_DRM_CONNECTOR_FLAGS_POLL	BIT(0)

	__u8 num_properties;
} __packed;

/*
 * struct gud_drm_req_get_connector_status - Connector status
 * @status: Status, see &drm_connector_status
 * @num_modes: Number of available display modes
 * @modes_array_checksum: CRC-CCITT checksum of the display mode array in little endian format
 * @edid_len: Length of EDID data
 * @edid_checksum: CRC-CCITT checksum of EDID data
 *
 * If both @num_modes and @edid_len are zero, connector status is set to
 * disconnected. If @num_modes is zero, edid is used to create display modes.
 * If both are set, edid is just passed on to userspace in the EDID connector
 * property.
 *
 * Display modes and EDID are only requested if number/length or crc differs.
 */
struct gud_drm_req_get_connector_status {
	__u8 status;
#define GUD_DRM_CONNECTOR_STATUS_MASK		0xf /* Only 2 bits are currently used for status */
#define GUD_DRM_CONNECTOR_STATUS_CHANGED	BIT(7)
	__le16 num_modes;
	__le16 edid_len;
} __packed;

/*
 * struct gud_drm_req_set_buffer - Set buffer transfer info
 * @x: X position of rectangle
 * @y: Y position
 * @width: Pixel width of rectangle
 * @height: Pixel height
 * @length: Buffer length in bytes
 * @compression: Transfer compression
 * @compressed_length: Compressed buffer length
 *
 * @x, @y, @width and @height specifies the rectangle where the buffer should be
 * placed inside the framebuffer.
 */
struct gud_drm_req_set_buffer {
	__le32 x;
	__le32 y;
	__le32 width;
	__le32 height;

	__le32 length;
	__u8 compression;
	__le32 compressed_length;
} __packed;

/*
 * struct gud_drm_req_set_state - Set display state
 * @mode: Display mode
 * @format: Pixel format
 * @connector: Connector index
 * @num_properties: Number of properties in the state
 * @properties: Array of properties
 *
 * The entire state is transferred each time there's a change.
 */
struct gud_drm_req_set_state {
	struct gud_drm_display_mode mode;
	__le32 format;
	__u8 connector;
	__u8 num_properties;
	struct gud_drm_property properties[];
} __packed;

/*
 * Internal monochrome transfer format presented to userspace as XRGB8888.
 * Pixel lines are byte aligned.
 */
//#define GUD_DRM_FORMAT_R1	fourcc_code('R', '1', ' ', ' ')

/* List of supported connector properties: */

/* TV related properties, see &drm_connector and &drm_tv_connector_state */
#define GUD_DRM_PROPERTY_TV_SELECT_SUBCONNECTOR		1
#define GUD_DRM_PROPERTY_TV_LEFT_MARGIN			2
#define GUD_DRM_PROPERTY_TV_RIGHT_MARGIN		3
#define GUD_DRM_PROPERTY_TV_TOP_MARGIN			4
#define GUD_DRM_PROPERTY_TV_BOTTOM_MARGIN		5
/* Number of modes are placed at _SHIFT in val on retrieval */
#define GUD_DRM_PROPERTY_TV_MODE			6
  #define GUD_DRM_USB_CONNECTOR_TV_MODE_NUM_SHIFT   16
#define GUD_DRM_PROPERTY_TV_BRIGHTNESS			7
#define GUD_DRM_PROPERTY_TV_CONTRAST			8
#define GUD_DRM_PROPERTY_TV_FLICKER_REDUCTION		9
#define GUD_DRM_PROPERTY_TV_OVERSCAN			10
#define GUD_DRM_PROPERTY_TV_SATURATION			11
#define GUD_DRM_PROPERTY_TV_HUE				12

/*
 * Backlight brightness is in the range 0-100 inclusive. The value represents
 * the human perceptual brightness and not a linear PWM value. 0 is minimum
 * brightness which should not turn the backlight completely off. The DPMS
 * connector property should be used to control power which will trigger a
 * GUD_DRM_USB_REQ_SET_DISPLAY_ENABLE request.
 *
 * This is not a real DRM property, but rather a fake one used for the backlight
 * device. See drm_backlight_register() for more details.
 */
#define GUD_DRM_PROPERTY_BACKLIGHT_BRIGHTNESS		13

/* List of supported properties that are not connector propeties: */

/*
 * Plane rotation. Should return the supported bitmask on
 * GUD_DRM_USB_REQ_GET_PROPERTIES, see drm_plane_create_rotation_property().
 */
#define GUD_DRM_PROPERTY_ROTATION			50

/* USB Control requests: */

/*
 * If the host driver doesn't support the device protocol version it will send
 * its version (u8). If the device isn't backwards compatible or doesn't support
 * the host version it shall halt the transfer. There is no status request
 * issued if this request fails/halts.
 */
#define GUD_DRM_USB_REQ_SET_VERSION			0x30

/* Get supported pixel formats as an array of fourcc codes. See include/uapi/drm/drm_fourcc.h */
#define GUD_DRM_USB_REQ_GET_FORMATS			0x40

/* Get supported properties that are not connector propeties as a &gud_drm_property array */
#define GUD_DRM_USB_REQ_GET_PROPERTIES			0x41

/* Get connector descriptor */
#define GUD_DRM_USB_REQ_GET_CONNECTOR			0x50

/* Get properties supported by the connector as a &gud_drm_property array */
#define GUD_DRM_USB_REQ_GET_CONNECTOR_PROPERTIES	0x51

/*
 * Issued when there's a tv.mode property present.
 * Gets an array of tv.mode enum names each entry of length DRM_PROP_NAME_LEN.
 */
#define GUD_DRM_USB_REQ_GET_CONNECTOR_TV_MODE_VALUES	0x52

/* When userspace checks status, this is issued first, not used for poll requests. */
#define GUD_DRM_USB_REQ_SET_CONNECTOR_FORCE_DETECT	0x53

/* Get connector status as &gud_drm_req_get_connector_status. */
#define GUD_DRM_USB_REQ_GET_CONNECTOR_STATUS		0x54

/* Get &gud_drm_display_mode array of supported display modes */
#define GUD_DRM_USB_REQ_GET_CONNECTOR_MODES		0x55

#define GUD_DRM_USB_REQ_GET_CONNECTOR_EDID		0x56

/* Set buffer properties before bulk transfer as &gud_drm_req_set_buffer */
#define GUD_DRM_USB_REQ_SET_BUFFER			0x60

/* Check display configuration as &gud_drm_req_set_state */
#define GUD_DRM_USB_REQ_SET_STATE_CHECK			0x61

/* Apply the prevoius _STATE_CHECK configuration */
#define GUD_DRM_USB_REQ_SET_STATE_COMMIT		0x62

 /* Enable/disable the display controller, value is u8 0/1 */
#define GUD_DRM_USB_REQ_SET_CONTROLLER_ENABLE		0x63

/* Enable/disable display/output (DPMS), value is u8 0/1 */
#define GUD_DRM_USB_REQ_SET_DISPLAY_ENABLE		0x64

#endif
