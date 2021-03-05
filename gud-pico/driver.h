// SPDX-License-Identifier: CC0-1.0

#ifndef _GUD_DRIVER_H_
#define _GUD_DRIVER_H_

#include "common/tusb_common.h"
#include "device/usbd.h"

struct gud_display;
void gud_driver_setup(const struct gud_display *disp, void *framebuffer, void *compress_buf);

#endif
