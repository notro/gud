// SPDX-License-Identifier: MIT
/*
 * Copyright 2021 Noralf Trønnes
 *
 * Based on libevdev/tools/libevdev-events.c:
 *
 * Copyright © 2013 Red Hat, Inc.
 */

#include <argp.h>
#include <assert.h>
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <linux/input.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <unistd.h>

#include "libevdev/libevdev.h"

#define REPORT_LENGTH	8
#define MAX_NUM_SLOTS	127

static bool verbose;
static bool debug;

size_t get_multitouch_report_desc(uint8_t *buf, unsigned int num_slots,
				  unsigned int min_x, unsigned int max_x,
				  unsigned int min_y, unsigned int max_y);

static void print_abs_bits(struct libevdev *dev, int axis)
{
	const struct input_absinfo *abs;

	if (!libevdev_has_event_code(dev, EV_ABS, axis))
		return;

	abs = libevdev_get_abs_info(dev, axis);

	printf("	Value	%6d\n", abs->value);
	printf("	Min	%6d\n", abs->minimum);
	printf("	Max	%6d\n", abs->maximum);
	if (abs->fuzz)
		printf("	Fuzz	%6d\n", abs->fuzz);
	if (abs->flat)
		printf("	Flat	%6d\n", abs->flat);
	if (abs->resolution)
		printf("	Resolution	%6d\n", abs->resolution);
}

static void print_code_bits(struct libevdev *dev, unsigned int type, unsigned int max)
{
	unsigned int i;
	for (i = 0; i <= max; i++) {
		if (!libevdev_has_event_code(dev, type, i))
			continue;

		printf("    Event code %i (%s)\n", i, libevdev_event_code_get_name(type, i));
		if (type == EV_ABS)
			print_abs_bits(dev, i);
	}
}

static void print_bits(struct libevdev *dev)
{
	unsigned int i;
	printf("Supported events:\n");

	for (i = 0; i <= EV_MAX; i++) {
		if (libevdev_has_event_type(dev, i))
			printf("  Event type %d (%s)\n", i, libevdev_event_type_get_name(i));
		switch(i) {
			case EV_KEY:
				print_code_bits(dev, EV_KEY, KEY_MAX);
				break;
			case EV_REL:
				print_code_bits(dev, EV_REL, REL_MAX);
				break;
			case EV_ABS:
				print_code_bits(dev, EV_ABS, ABS_MAX);
				break;
			case EV_LED:
				print_code_bits(dev, EV_LED, LED_MAX);
				break;
		}
	}
}

static void print_props(struct libevdev *dev)
{
	unsigned int i;
	printf("Properties:\n");

	for (i = 0; i <= INPUT_PROP_MAX; i++) {
		if (libevdev_has_property(dev, i))
			printf("  Property type %d (%s)\n", i,
					libevdev_property_get_name(i));
	}
}

static int print_event(struct input_event *ev)
{
	if (ev->type == EV_SYN)
		printf("Event: time %ld.%06ld, ++++++++++++++++++++ %s +++++++++++++++\n",
				ev->input_event_sec,
				ev->input_event_usec,
				libevdev_event_type_get_name(ev->type));
	else
		printf("Event: time %ld.%06ld, type %d (%s), code %d (%s), value %d\n",
			ev->input_event_sec,
			ev->input_event_usec,
			ev->type,
			libevdev_event_type_get_name(ev->type),
			ev->code,
			libevdev_event_code_get_name(ev->type, ev->code),
			ev->value);
	return 0;
}

static int print_sync_event(struct input_event *ev)
{
	printf("SYNC: ");
	print_event(ev);
	return 0;
}

struct touch_slot {
	int id; // -1 means no touch
	unsigned int x;
	unsigned int y;
	bool active;
};

struct touch_state {
	bool multitouch;
	struct touch_slot *slots;
	unsigned int num_slots;
	int current_slot;
	bool btn_touch;
};

void store_le16(uint8_t *ptr, uint16_t val)
{
	ptr[0] = val & 0xff;
	ptr[1] = val >> 8;
}

static void handle_event(struct touch_state *state, struct input_event *ev)
{
	struct touch_slot *slot;

	if (!state->multitouch) {
		slot = &state->slots[0];

		if (ev->type == EV_KEY && ev->code == BTN_TOUCH) {
			slot->id = ev->value ? 0 : -1;
			slot->active = true;
		} else if (ev->type == EV_ABS) {
			switch (ev->code) {
			case ABS_X:
				slot->x = ev->value;
				break;
			case ABS_Y:
				slot->y = ev->value;
				break;
			}
		}
		return;
	}

	if (ev->type != EV_ABS)
		return;

	if (ev->code == ABS_MT_SLOT) {
		if (ev->value < state->num_slots)
			state->current_slot = ev->value;
		else
			fprintf(stderr, "%s: ABS_MT_SLOT=%u is out of bounds\n", __func__, ev->value);
		return;
	}

	slot = &state->slots[state->current_slot];

	switch (ev->code) {
	case ABS_MT_TRACKING_ID:
		slot->id = ev->value;
		if (ev->value != -1)
			slot->active = true;
		break;
	case ABS_MT_POSITION_X:
		slot->x = ev->value;
		break;
	case ABS_MT_POSITION_Y:
		slot->y = ev->value;
		break;
	}
}

static void send_report(int fd, struct touch_state *state, struct input_event *ev)
{
	uint8_t report[MAX_NUM_SLOTS * REPORT_LENGTH], *p = report;
	uint8_t contact_count = 0;
	struct touch_slot *slot;
	uint16_t scantime;
	int i, rc;

	// unit is 100us
	scantime = (ev->input_event_sec * 10000) + (ev->input_event_usec / 100);
	if (debug)
		printf("%s: scantime=%u:\n", __func__, scantime);

	for (i = 0; i < state->num_slots; i++) {
		slot = &state->slots[i];
		if (!slot->active)
			continue;

		if (debug)
			printf("  i=%d: cc=%u id=%d x=%u y=%u\n",
				i, contact_count, slot->id, slot->x, slot->y);

		p[0] = (contact_count << 1) | (slot->id >= 0); // Contact Identifier[7:1] Tip Switch[0]
		store_le16(p + 1, slot->x);
		store_le16(p + 3, slot->y);
		store_le16(p + 5, scantime);
		p[7] = 0; // Contact Count is zero on all but the first, which is filled in later

		if (slot->id < 0)
			slot->active = false;

		contact_count++;
		p += REPORT_LENGTH;
	}

	if (!contact_count) {
		fprintf(stderr, "%s: contact_count is unexpectedly zero\n", __func__);
		return;
	}

	report[7] = contact_count;

	for (p = report, i = 0; i < contact_count; i++, p += REPORT_LENGTH) {
		rc = write(fd, p, REPORT_LENGTH);
		if (rc < 0)
			perror("Failed to send hid report");
		else if (rc != REPORT_LENGTH)
			fprintf(stderr, "Failed to send hid report: rc=%d != REPORT_LENGTH\n", rc);
	}
}

static int get_num_slots(struct libevdev *dev, bool test)
{
	unsigned int num_slots;

	if (!libevdev_has_event_code(dev, EV_KEY, BTN_TOUCH)) {
		if (!test || verbose)
			fprintf(stderr, "Input device is missing BTN_TOUCH\n");
		return -1;
	}

	if (libevdev_has_event_code(dev, EV_ABS, ABS_MT_SLOT)) {
		const struct input_absinfo *abs;

		if (!libevdev_has_event_code(dev, EV_ABS, ABS_MT_POSITION_X) ||
		    !libevdev_has_event_code(dev, EV_ABS, ABS_MT_POSITION_Y)) {
			if (!test || verbose)
				fprintf(stderr, "Input device is missing ABS_MT_POSITION_X/Y\n");
			return -1;
		}

		abs = libevdev_get_abs_info(dev, ABS_MT_SLOT);
		num_slots = abs->maximum;
		if (num_slots < 1 || num_slots > MAX_NUM_SLOTS) {
			if (!test || verbose)
				fprintf(stderr, "ABS_MT_SLOT=%d is out of bounds\n", num_slots);
			return -1;
		}
	} else {
		if (!libevdev_has_event_code(dev, EV_ABS, ABS_X) ||
		    !libevdev_has_event_code(dev, EV_ABS, ABS_Y)) {
			if (!test || verbose)
				fprintf(stderr, "Input device is missing ABS_X/Y\n");
			return -1;
		}

		num_slots = 1;
	}

	return num_slots;
}

static int open_evdev(const char *file, struct libevdev **dev)
{
	int fd, rc;

	fd = open(file, O_RDONLY);
	if (fd < 0) {
		perror(file);
		return 1;
	}

	rc = libevdev_new_from_fd(fd, dev);
	if (rc < 0) {
		fprintf(stderr, "Failed to init libevdev for '%s' (%s)\n", file,  strerror(-rc));
		close(fd);
		return rc;
	}

	return 0;
}

static void close_evdev(struct libevdev *dev)
{
	close(libevdev_get_fd(dev));
	libevdev_free(dev);
}

static int is_event_device(const struct dirent *dir)
{
	return strncmp("event", dir->d_name, 5) == 0;
}

static int find_touch_device(void)
{
	struct dirent **namelist;
	struct libevdev *dev;
	int i, ndev;

	ndev = scandir("/dev/input", &namelist, is_event_device, alphasort);
	if (ndev <= 0)
		return 1;

	for (i = 0; i < ndev; i++)
	{
		char fname[4096];
		bool found = false;
		int rc;

		snprintf(fname, sizeof(fname),
			 "/dev/input/%s", namelist[i]->d_name);

		rc = open_evdev(fname, &dev);
		if (rc)
			continue;

		if (verbose)
			fprintf(stderr, "Input device ID: bus %#x vendor %#x product %#x\n",
				libevdev_get_id_bustype(dev),
				libevdev_get_id_vendor(dev),
				libevdev_get_id_product(dev));

		if (get_num_slots(dev, true) > 0)
			found = true;

		close_evdev(dev);

		if (found) {
			printf(fname);
			return 0;
		}
	}

	return 2;
}

const char *argp_program_version = "hid-touch-bridge 0.1";
static char doc[] = "Bridge between touch device and HID gadget.";
static char args_doc[] = "[INPUT DEVICE [HIDG DEVICE]]";

enum commandline_options {
	OPTION_VERBOSE = 'v',
	OPTION_DEBUG = 'd',
	OPTION_FIND = 0x100,
	OPTION_DESC,
	OPTION_LENGTH,
};

static struct argp_option options[] = {
	{ "find", OPTION_FIND, 0, 0, "Print the first touch device."},
	{ "desc", OPTION_DESC, 0, 0, "Print HIDG descriptor for input device."},
	{ "length", OPTION_LENGTH, 0, 0, "Print HIDG report length for input device."},
	{ 0, OPTION_VERBOSE, 0, 0, "Be verbose."},
	{ 0, OPTION_DEBUG, 0, 0, "Print debug info."},
	{ 0 }
};

struct arguments {
	bool find;
	bool desc;
	bool length;
	const char *ev;
	const char *hidg;
};

static error_t parse_options(int key, char *arg, struct argp_state *state)
{
	struct arguments *arguments = state->input;

	switch (key) {
	case OPTION_FIND: arguments->find = true; return 0;
	case OPTION_DESC: arguments->desc = true; return 0;
	case OPTION_LENGTH: arguments->length = true; return 0;
	case OPTION_VERBOSE: verbose = true; return 0;
	case OPTION_DEBUG: debug = true; return 0;
	case ARGP_KEY_ARG:
		if (state->arg_num > 1)
			return ARGP_ERR_UNKNOWN;
		if (state->arg_num == 0)
			arguments->ev = arg;
		else
			arguments->hidg = arg;
		return 0;
	}
	return ARGP_ERR_UNKNOWN;
}

static struct argp argp = { options, parse_options, args_doc, doc, 0, 0, 0 };

int main(int argc, char **argv)
{
	struct arguments arguments = { 0 };
	struct touch_state *state = NULL;
	struct touch_slot *slots = NULL;
	struct libevdev *dev = NULL;
	int num_slots;
	int rc = 1;
	int hidfd;

	if (argc == 1) {
		argp_help(&argp, stdout, ARGP_HELP_USAGE, "hid-touch-bridge");
		return 1;
	}

	argp_parse(&argp, argc, argv, 0, 0, &arguments);

	if (arguments.find) {
		if (arguments.ev || arguments.hidg) {
			fprintf(stderr, "--find does not take arguments\n");
			return 1;
		}
		return find_touch_device();
	}

	if (!arguments.ev) {
		fprintf(stderr, "Event device missing\n");
		return 1;
	}

	rc = open_evdev(arguments.ev, &dev);
	if (rc)
		return rc;

	if (verbose) {
		printf("Input device ID: bus %#x vendor %#x product %#x\n",
		       libevdev_get_id_bustype(dev), libevdev_get_id_vendor(dev), libevdev_get_id_product(dev));
		printf("Evdev version: %x\n", libevdev_get_driver_version(dev));
		printf("Input device name: \"%s\"\n", libevdev_get_name(dev));
		printf("Phys location: %s\n", libevdev_get_phys(dev));
		printf("Uniq identifier: %s\n", libevdev_get_uniq(dev));
		print_bits(dev);
		print_props(dev);
	}

	num_slots = get_num_slots(dev, false);
	if (num_slots < 1) {
		rc = 1;
		goto out;
	}

	if (arguments.desc || arguments.length) {
		if (arguments.hidg) {
			fprintf(stderr, "--desc and --length takes exactly one argument\n");
			rc = 1;
			goto out;
		}

		if (arguments.desc) {
			const struct input_absinfo *abs_x, *abs_y;
			uint8_t buf[1024];
			size_t size;

			abs_x = libevdev_get_abs_info(dev, ABS_X);
			abs_y = libevdev_get_abs_info(dev, ABS_Y);
			size = get_multitouch_report_desc(buf, num_slots,
							  abs_x->minimum, abs_x->maximum,
							  abs_y->minimum, abs_y->maximum);
			rc = fwrite(buf, size, 1, stdout);
			rc = rc != size ? 1 : 0;
		} else {
			printf("%u", REPORT_LENGTH);
			rc = 0;
		}

		goto out;
	}

	if (!arguments.hidg) {
		fprintf(stderr, "HIDG device missing\n");
		rc = 1;
		goto out;
	}

	state = malloc(sizeof(*state));
	slots = malloc(sizeof(*slots) * num_slots);
	if (!state || !slots) {
		fprintf(stderr, "Failed to allocate state\n");
		rc = 1;
		goto out;
	}

	state->slots = slots;
	state->num_slots = num_slots;
	state->multitouch = libevdev_has_event_code(dev, EV_ABS, ABS_MT_SLOT);

	if ((hidfd = open(arguments.hidg, O_RDWR, 0666)) < 0) {
		perror(arguments.hidg);
		rc = 1;
		goto out;
	}

	do {
		struct input_event ev;
		rc = libevdev_next_event(dev, LIBEVDEV_READ_FLAG_NORMAL|LIBEVDEV_READ_FLAG_BLOCKING, &ev);
		if (rc == LIBEVDEV_READ_STATUS_SYNC) {
			printf("::::::::::::::::::::: dropped ::::::::::::::::::::::\n");
			while (rc == LIBEVDEV_READ_STATUS_SYNC) {
				print_sync_event(&ev);
				rc = libevdev_next_event(dev, LIBEVDEV_READ_FLAG_SYNC, &ev);
			}
			printf("::::::::::::::::::::: re-synced ::::::::::::::::::::::\n");
		} else if (rc == LIBEVDEV_READ_STATUS_SUCCESS) {
			if (debug)
				print_event(&ev);
			if (ev.type == EV_SYN)
				send_report(hidfd, state, &ev);
			else
				handle_event(state, &ev);
		}
	} while (rc == LIBEVDEV_READ_STATUS_SYNC || rc == LIBEVDEV_READ_STATUS_SUCCESS || rc == -EAGAIN);

	if (rc != LIBEVDEV_READ_STATUS_SUCCESS && rc != -EAGAIN)
		fprintf(stderr, "Failed to handle events: %s\n", strerror(-rc));

	rc = 0;
out:
	free(state);
	free(slots);
	close_evdev(dev);

	return rc;
}
