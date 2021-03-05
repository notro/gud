// SPDX-License-Identifier: CC0-1.0

#include <string.h>
#include "tusb.h"
#include "pico/unique_id.h"

tusb_desc_device_t const device_descriptor = {
    .bLength            = sizeof(tusb_desc_device_t),
    .bDescriptorType    = TUSB_DESC_DEVICE,
    .bcdUSB          	= 0x0110, // USB 1.1 device

    .bDeviceClass    	= 0,      // Specified in interface descriptor
    .bDeviceSubClass 	= 0,      // No subclass
    .bDeviceProtocol 	= 0,      // No protocol
    .bMaxPacketSize0 	= 64,     // Max packet size for ep0

    .idVendor        	= 0x1d50,
    .idProduct       	= 0x614d,
    .bcdDevice       	= 0,      // Device revision number

    .iManufacturer      = 1,
    .iProduct           = 2,
    .iSerialNumber 	    = 3,

    .bNumConfigurations = 1
};

uint8_t const *tud_descriptor_device_cb(void)
{
    return (uint8_t const *) &device_descriptor;
}

typedef struct TU_ATTR_PACKED {
    tusb_desc_configuration_t config;
    tusb_desc_interface_t interface;
    tusb_desc_endpoint_t bulk_out;
} gud_display_config_descriptor_t;

gud_display_config_descriptor_t config_descriptor = {
    .config = {
        .bLength = sizeof(tusb_desc_configuration_t),
        .bDescriptorType = TUSB_DESC_CONFIGURATION,
        .wTotalLength = sizeof(gud_display_config_descriptor_t),
        .bNumInterfaces = 1,
        .bConfigurationValue = 1,
        .iConfiguration = 0,
        .bmAttributes = TU_BIT(7) | TUSB_DESC_CONFIG_ATT_SELF_POWERED,
        .bMaxPower = 100 / 2,
    },

    .interface = {
        .bLength = sizeof(tusb_desc_interface_t),
        .bDescriptorType = TUSB_DESC_INTERFACE,
        .bInterfaceNumber = 0,
        .bAlternateSetting = 0,
        .bNumEndpoints = 1,
        .bInterfaceClass = TUSB_CLASS_VENDOR_SPECIFIC,
        .bInterfaceSubClass = 0x00,
        .bInterfaceProtocol = 0x00,
        .iInterface = 0,
    },

    .bulk_out = {
        .bLength = sizeof(tusb_desc_endpoint_t),
        .bDescriptorType = TUSB_DESC_ENDPOINT,
        .bEndpointAddress = 3,
        .bmAttributes = TUSB_XFER_BULK,
        .wMaxPacketSize.size = CFG_GUD_BULK_OUT_SIZE,
    },
};

uint8_t const * tud_descriptor_configuration_cb(uint8_t index)
{
    (void) index;
    return (uint8_t const *)&config_descriptor;
}

typedef struct TU_ATTR_PACKED
{
    uint8_t bLength;
    uint8_t bDescriptorType;
    uint16_t unicode_string[31];
} gud_desc_string_t;

static gud_desc_string_t string_descriptor = {
    .bDescriptorType = TUSB_DESC_STRING,
};

uint16_t const *tud_descriptor_string_cb(uint8_t index, uint16_t langid)
{
    (void) langid;

    if (index == 0) {
        string_descriptor.bLength = 4;
        string_descriptor.unicode_string[0] = 0x0409;
        return (uint16_t *)&string_descriptor;
    }

    const char *str;
    char serial[17];

    if (index == 1) {
        str = "Raspberry Pi";
    } else if (index == 2) {
        str = "Pico GUD Display";
    } else if (index == 3) {
        pico_unique_board_id_t id_out;
        pico_get_unique_board_id(&id_out);
        snprintf(serial, sizeof(serial), "%016llx", *((uint64_t*)(id_out.id)));
        str = serial;
    } else {
        return NULL;
    }

    uint8_t len = strlen(str);
    if (len > sizeof(string_descriptor.unicode_string))
        len = sizeof(string_descriptor.unicode_string);

    string_descriptor.bLength = 2 + 2 * len;

    for (uint8_t i = 0; i < len; i++)
      string_descriptor.unicode_string[i] = str[i];

    return (uint16_t *)&string_descriptor;
}
