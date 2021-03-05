// SPDX-License-Identifier: CC0-1.0

#include <stdlib.h>
#include <stdio.h>
#include <string.h>

#include "bsp/board.h"
#include "tusb.h"
#include "hardware/gpio.h"
#include "hardware/pwm.h"
#include "pico/unique_id.h"

#include "driver.h"
#include "gud.h"
#include "mipi_dbi.h"

#define LOG
#define LOG2
#define LOG3

/*
 * 0 = led off
 * 1 = power led, off while flushing
 * 2 = on while flushing
 */
#define LED_ACTION  1

#define BL_GPIO 20
#define BL_DEF_LEVEL 100

#define WIDTH   240
#define HEIGHT  135

uint16_t framebuffer[WIDTH * HEIGHT];
uint16_t compress_buf[WIDTH * HEIGHT];

static const struct mipi_dbi dbi = {
    .spi = spi0,
    .sck = 18,
    .mosi = 19,
    .cs = 17,
    .dc = 16,
    .baudrate = 64 * 1024 * 1024, // 64MHz
};

// https://jared.geek.nz/2013/feb/linear-led-pwm
static const uint16_t cie1931[101] = {
    36, 73, 145, 218, 290, 363, 435, 508, 580, 608,
    684, 765, 854, 948, 1050, 1159, 1274, 1398, 1529, 1667,
    1814, 1970, 2134, 2307, 2489, 2680, 2881, 3092, 3313, 3544,
    3785, 4038, 4301, 4575, 4861, 5159, 5468, 5790, 6124, 6470,
    6830, 7202, 7588, 7987, 8400, 8827, 9268, 9724, 10195, 10680,
    11181, 11697, 12228, 12776, 13339, 13919, 14515, 15129, 15759, 16407,
    17072, 17754, 18455, 19174, 19911, 20667, 21442, 22237, 23050, 23883,
    24736, 25609, 26502, 27416, 28350, 29306, 30283, 31281, 32301, 33343,
    34407, 35493, 36602, 37734, 38890, 40068, 41270, 42496, 43745, 45019,
    46318, 47641, 48990, 50363, 51762, 53186, 54637, 56114, 57617, 59146,
    60702,
};

static uint brightness = BL_DEF_LEVEL;

static void backlight_set(int level)
{
    uint16_t pwm;

    LOG("Set backlight: %d\n", level);
    if (level > 100)
        return;

    if (level < 0)
        pwm = 0;
    else
        pwm = cie1931[level];

    pwm_set_gpio_level(BL_GPIO, pwm);
}

static void backlight_init(uint gpio)
{
    pwm_config cfg = pwm_get_default_config();
    pwm_set_wrap(pwm_gpio_to_slice_num(gpio), 65535);
    pwm_init(pwm_gpio_to_slice_num(gpio), &cfg, true);
    gpio_set_function(gpio, GPIO_FUNC_PWM);
}

static int controller_enable(const struct gud_display *disp, uint8_t enable)
{
    LOG("%s: enable=%u\n", __func__, enable);
    return 0;
}

static int display_enable(const struct gud_display *disp, uint8_t enable)
{
    LOG("%s: enable=%u\n", __func__, enable);

    if (enable)
        backlight_set(brightness);
    else
        backlight_set(-1);

    return 0;
}

static int state_commit(const struct gud_display *disp, const struct gud_state_req *state, uint8_t num_properties)
{
    LOG("%s: mode=%ux%u format=0x%02x connector=%u num_properties=%u\n",
        __func__, state->mode.hdisplay, state->mode.vdisplay, state->format, state->connector, num_properties);

    for (uint8_t i = 0; i < num_properties; i++) {
        const struct gud_property_req *prop = &state->properties[i];
        LOG("  prop=%u val=%llu\n", prop->prop, prop->val);
        switch (prop->prop) {
            case GUD_PROPERTY_BACKLIGHT_BRIGHTNESS:
                brightness = prop->val;
                backlight_set(brightness);
                break;
            default:
                LOG("Unknown property: %u\n", prop->prop);
                break;
        };
    }

    return 0;
}

static int set_buffer(const struct gud_display *disp, const struct gud_set_buffer_req *set_buf)
{
    LOG3("%s: x=%u y=%u width=%u height=%u length=%u compression=0x%x\n", __func__,
         set_buf->x, set_buf->y, set_buf->width, set_buf->height, set_buf->length, set_buf->compression);

    if (LED_ACTION == 1)
        board_led_write(false);
    else if (LED_ACTION == 2)
        board_led_write(true);

    return 0;
}

static void write_buffer(const struct gud_display *disp, const struct gud_set_buffer_req *set_buf, void *buf)
{
    LOG2("%s: x=%u y=%u width=%u height=%u length=%u compression=0x%x\n", __func__,
         set_buf->x, set_buf->y, set_buf->width, set_buf->height, set_buf->length, set_buf->compression);

    mipi_dbi_update16(&dbi, set_buf->x + 40, set_buf->y + 53, set_buf->width, set_buf->height, buf, set_buf->length);

    if (LED_ACTION == 1)
        board_led_write(true);
    else if (LED_ACTION == 2)
        board_led_write(false);
}

static const uint8_t pixel_formats[] = {
    GUD_PIXEL_FORMAT_RGB565,
};

static const struct gud_property_req connector_properties[] = {
    {
        .prop = GUD_PROPERTY_BACKLIGHT_BRIGHTNESS,
        .val = BL_DEF_LEVEL,
    },
};

static uint32_t gud_display_edid_get_serial_number(void)
{
    pico_unique_board_id_t id_out;

    pico_get_unique_board_id(&id_out);
    return *((uint64_t*)(id_out.id));
}

static const struct gud_display_edid edid = {
    .name = "pico display",
    .pnp = "PIM",
    .product_code = 0x01,
    .year = 2021,
    .width_mm = 27,
    .height_mm = 16,

    .get_serial_number = gud_display_edid_get_serial_number,
};

const struct gud_display display = {
    .width = WIDTH,
    .height = HEIGHT,

    .compression = GUD_COMPRESSION_LZ4,

    .formats = pixel_formats,
    .num_formats = 1,

    .connector_properties = connector_properties,
    .num_connector_properties = 1,

    .edid = &edid,

    .controller_enable = controller_enable,
    .display_enable = display_enable,

    .state_commit = state_commit,

    .set_buffer = set_buffer,
    .write_buffer = write_buffer,
};

static void init_display(void)
{
    backlight_init(BL_GPIO);
    mipi_dbi_spi_init(&dbi);

    mipi_dbi_command(&dbi, MIPI_DCS_SOFT_RESET);

    sleep_ms(150);

    mipi_dbi_command(&dbi, MIPI_DCS_SET_ADDRESS_MODE, 0x70);
    mipi_dbi_command(&dbi, MIPI_DCS_SET_PIXEL_FORMAT, MIPI_DCS_PIXEL_FORMAT_16BIT);

    mipi_dbi_command(&dbi, MIPI_DCS_ENTER_INVERT_MODE);
    mipi_dbi_command(&dbi, MIPI_DCS_EXIT_SLEEP_MODE);
    mipi_dbi_command(&dbi, MIPI_DCS_SET_DISPLAY_ON);

    sleep_ms(100);

    // Clear display
    mipi_dbi_update16(&dbi, 40, 53, WIDTH, HEIGHT, framebuffer, WIDTH * HEIGHT * 2);
}

static void pwm_gpio_init(uint gpio, uint16_t val)
{
    pwm_config cfg = pwm_get_default_config();
    pwm_config_set_output_polarity(&cfg, true, true);
    pwm_set_wrap(pwm_gpio_to_slice_num(gpio), 65535);
    pwm_init(pwm_gpio_to_slice_num(gpio), &cfg, true);
    gpio_set_function(gpio, GPIO_FUNC_PWM);
    pwm_set_gpio_level(gpio, val);
}

static void turn_off_rgb_led(void)
{
    pwm_gpio_init(6, 0);
    pwm_gpio_init(7, 0);
    pwm_gpio_init(8, 0);
}

int main(void)
{
    board_init();

    if (LED_ACTION)
        board_led_write(true);

    init_display();

    gud_driver_setup(&display, framebuffer, compress_buf);

    tusb_init();

    LOG("\n\n%s: CFG_TUSB_DEBUG=%d\n", __func__, CFG_TUSB_DEBUG);

    turn_off_rgb_led();

    while (1)
    {
        tud_task(); // tinyusb device task
    }

    return 0;
}

void tud_mount_cb(void)
{
    LOG("%s:\n", __func__);
    if (LED_ACTION == 2)
        board_led_write(false);
}
