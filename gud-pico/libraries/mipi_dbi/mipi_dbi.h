// SPDX-License-Identifier: CC0-1.0

#ifndef _MIPI_DBI_H_
#define _MIPI_DBI_H_

#include "hardware/spi.h"

struct mipi_dbi {
    spi_inst_t *spi;
    spi_cpol_t cpol;
    spi_cpha_t cpha;
    uint sck;
    uint mosi;
    uint cs;
    uint dc;
    uint baudrate;
};

#define mipi_dbi_command(dbi, cmd, seq...) \
({ \
	const uint8_t d[] = { seq }; \
	mipi_dbi_command_buf(dbi, cmd, d, sizeof(d)); \
})

enum {
    MIPI_DCS_NOP                    = 0x00,
    MIPI_DCS_SOFT_RESET             = 0x01,
    MIPI_DCS_GET_RED_CHANNEL        = 0x06,
    MIPI_DCS_GET_GREEN_CHANNEL      = 0x07,
    MIPI_DCS_GET_BLUE_CHANNEL       = 0x08,
    MIPI_DCS_GET_POWER_MODE         = 0x0A,
    MIPI_DCS_GET_ADDRESS_MODE       = 0x0B,
    MIPI_DCS_GET_PIXEL_FORMAT       = 0x0C,
    MIPI_DCS_GET_DISPLAY_MODE       = 0x0D,
    MIPI_DCS_GET_SIGNAL_MODE        = 0x0E,
    MIPI_DCS_GET_DIAGNOSTIC_RESULT  = 0x0F,
    MIPI_DCS_ENTER_SLEEP_MODE       = 0x10,
    MIPI_DCS_EXIT_SLEEP_MODE        = 0x11,
    MIPI_DCS_ENTER_PARTIAL_MODE     = 0x12,
    MIPI_DCS_ENTER_NORMAL_MODE      = 0x13,
    MIPI_DCS_EXIT_INVERT_MODE       = 0x20,
    MIPI_DCS_ENTER_INVERT_MODE      = 0x21,
    MIPI_DCS_SET_GAMMA_CURVE        = 0x26,
    MIPI_DCS_SET_DISPLAY_OFF        = 0x28,
    MIPI_DCS_SET_DISPLAY_ON         = 0x29,
    MIPI_DCS_SET_COLUMN_ADDRESS     = 0x2A,
    MIPI_DCS_SET_PAGE_ADDRESS       = 0x2B,
    MIPI_DCS_WRITE_LUT              = 0x2D,
    MIPI_DCS_WRITE_MEMORY_START     = 0x2C,
    MIPI_DCS_READ_MEMORY_START      = 0x2E,
    MIPI_DCS_SET_PARTIAL_AREA       = 0x30,
    MIPI_DCS_SET_SCROLL_AREA        = 0x33,
    MIPI_DCS_SET_TEAR_OFF           = 0x34,
    MIPI_DCS_SET_TEAR_ON            = 0x35,
    MIPI_DCS_SET_ADDRESS_MODE       = 0x36,
    MIPI_DCS_SET_SCROLL_START       = 0x37,
    MIPI_DCS_EXIT_IDLE_MODE         = 0x38,
    MIPI_DCS_ENTER_IDLE_MODE        = 0x39,
    MIPI_DCS_SET_PIXEL_FORMAT       = 0x3A,
    MIPI_DCS_WRITE_MEMORY_CONTINUE  = 0x3C,
    MIPI_DCS_READ_MEMORY_CONTINUE   = 0x3E,
    MIPI_DCS_SET_TEAR_SCANLINE      = 0x44,
    MIPI_DCS_GET_SCANLINE           = 0x45,
    MIPI_DCS_READ_DDB_START         = 0xA1,
    MIPI_DCS_READ_DDB_CONTINUE      = 0xA8,
};

enum {
    MIPI_DCS_PIXEL_FORMAT_24BIT     = 7,
    MIPI_DCS_PIXEL_FORMAT_18BIT     = 6,
    MIPI_DCS_PIXEL_FORMAT_16BIT     = 5,
    MIPI_DCS_PIXEL_FORMAT_12BIT     = 3,
    MIPI_DCS_PIXEL_FORMAT_8BIT      = 2,
    MIPI_DCS_PIXEL_FORMAT_3BIT      = 1,
};

void mipi_dbi_spi_init(const struct mipi_dbi *dbi);

void mipi_dbi_command_buf(const struct mipi_dbi *dbi, uint8_t cmd, const uint8_t *data, size_t len);

void mipi_dbi_set_window(const struct mipi_dbi *dbi,
                         uint16_t x, uint16_t y,
                         uint16_t width, uint16_t height);
void mipi_dbi_update16(const struct mipi_dbi *dbi, uint16_t x, uint16_t y,
                       uint16_t width, uint16_t height, void *buf, size_t len);
void mipi_dbi_update_wait(const struct mipi_dbi *dbi);

void mipi_dbi_hw_reset(uint gpio);


#endif
