/* SPDX-License-Identifier: CC0-1.0 */

#ifndef _GUD_H_
#define _GUD_H_

#include <stdint.h>
#include "gud_drm.h"

#if defined(__cplusplus)
extern "C" {
#endif


struct framebuffer {
	unsigned int width;
	unsigned int height;

	unsigned int cpp;
	unsigned int pitch;
};

struct gud_drm_gadget {
	struct framebuffer fb;

	uint8_t errno;

	struct gud_drm_req_set_state state;

	struct gud_drm_req_set_buffer req_set_buffer;

	uint8_t brightness;
	uint8_t check_ok;

	size_t max_buffer_size;
};

int gud_drm_gadget_write_buffer(struct gud_drm_gadget *gdg, void *fb_address, const void *buf, size_t len);
int gud_drm_gadget_set_buffer(struct gud_drm_gadget *gdg, struct gud_drm_req_set_buffer *req);
int gud_drm_gadget_ctrl_get(struct gud_drm_gadget *gdg, uint8_t request,
			    uint16_t index, void *data, uint16_t size);
int gud_drm_gadget_ctrl_set(struct gud_drm_gadget *gdg, uint8_t request,
			    uint16_t index, void *data, uint16_t size);
void gud_drm_gadget_init(struct gud_drm_gadget *gdg, uint32_t width, uint32_t height, size_t len);



#if defined(__cplusplus)
}
#endif

#endif
