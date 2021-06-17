/* Teensyduino Core Library
 * http://www.pjrc.com/teensy/
 * Copyright (c) 2017 PJRC.COM, LLC.
 *
 * Permission is hereby granted, free of charge, to any person obtaining
 * a copy of this software and associated documentation files (the
 * "Software"), to deal in the Software without restriction, including
 * without limitation the rights to use, copy, modify, merge, publish,
 * distribute, sublicense, and/or sell copies of the Software, and to
 * permit persons to whom the Software is furnished to do so, subject to
 * the following conditions:
 *
 * 1. The above copyright notice and this permission notice shall be
 * included in all copies or substantial portions of the Software.
 *
 * 2. If the Software is incorporated into a build system that allows
 * selection among a list of target devices, then similar target
 * devices manufactured by PJRC.COM must be included in the list of
 * target devices and selectable in the same manner.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
 * EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
 * MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
 * NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS
 * BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN
 * ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
 * CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
 * SOFTWARE.
 */

#include <stddef.h>
#include <stdint.h>
#include <string.h>

void store_le16(uint8_t *ptr, uint16_t val);

// Source: https://github.com/PaulStoffregen/cores/blob/master/teensy3/usb_desc.c
// Change: Removed Pressure and given X/Y their own max/min.
static const uint8_t multitouch_report_desc[] = {
	0x05, 0x0D,                     // Usage Page (Digitizer)
	0x09, 0x04,                     // Usage (Touch Screen)
	0xa1, 0x01,                     // Collection (Application)
	0x09, 0x22,                     //   Usage (Finger)
	0xA1, 0x02,                     //   Collection (Logical)

	0x09, 0x42,                     //     Usage (Tip Switch)
	0x15, 0x00,                     //     Logical Minimum (0)
	0x25, 0x01,                     //     Logical Maximum (1)
	0x75, 0x01,                     //     Report Size (1)
	0x95, 0x01,                     //     Report Count (1)
	0x81, 0x02,                     //     Input (variable,absolute)

	0x09, 0x51,                     //     Usage (Contact Identifier)
	0x25, 0x7F,                     //     Logical Maximum (127)
	0x75, 0x07,                     //     Report Size (7)
	0x95, 0x01,                     //     Report Count (1)
	0x81, 0x02,                     //     Input (variable,absolute)

	0x05, 0x01,                     //     Usage Page (Generic Desktop)
	0x65, 0x00,                     //     Unit (None)
	0x75, 0x10,                     //     Report Size (16)
	0x95, 0x01,                     //     Report Count (1)

	0x09, 0x30,                     //     Usage (X)
	0x16, 0x00, 0x00,               //     Logical Minimum (n)
	0x26, 0x00, 0x00,               //     Logical Maximum (n)
	0x81, 0x02,                     //     Input (variable,absolute)

	0x09, 0x31,                     //     Usage (Y)
	0x16, 0x00, 0x00,               //     Logical Minimum (n)
	0x26, 0x00, 0x00,               //     Logical Maximum (n)
	0x81, 0x02,                     //     Input (variable,absolute)

	0xC0,                           //   End Collection

	0x05, 0x0D,                     //   Usage Page (Digitizer)
	0x15, 0x00,                     //   Logical Minimum (0)
	0x27, 0xFF, 0xFF, 0, 0,         //   Logical Maximum (65535)
	0x75, 0x10,                     //   Report Size (16)
	0x95, 0x01,                     //   Report Count (1)

	0x09, 0x56,                     //   Usage (Scan Time)
	0x81, 0x02,                     //   Input (variable,absolute)

	0x09, 0x54,                     //   USAGE (Contact count)
	0x25, 0x7f,                     //   LOGICAL_MAXIMUM (127)
	0x95, 0x01,                     //   REPORT_COUNT (1)
	0x75, 0x08,                     //   REPORT_SIZE (8)
	0x81, 0x02,                     //   INPUT (Data,Var,Abs)

	0x05, 0x0D,                     //   Usage Page (Digitizers)
	0x09, 0x55,                     //   Usage (Contact Count Maximum)
	0x25, 0x00,                     //   Logical Maximum (n)
	0x75, 0x08,                     //   Report Size (8)
	0x95, 0x01,                     //   Report Count (1)
	0xB1, 0x02,                     //   Feature (variable,absolute)
	0xC0                            // End Collection
};

size_t get_multitouch_report_desc(uint8_t *buf, unsigned int num_slots,
				  unsigned int min_x, unsigned int max_x,
				  unsigned int min_y, unsigned int max_y)
{
	memcpy(buf, multitouch_report_desc, sizeof(multitouch_report_desc));

	store_le16(buf + 43, min_x);
	store_le16(buf + 46, max_x);
	store_le16(buf + 53, min_y);
	store_le16(buf + 56, max_y);
	buf[93] = num_slots;

	return sizeof(multitouch_report_desc);
}
