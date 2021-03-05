// SPDX-License-Identifier: CC0-1.0

#include "hardware/dma.h"
#include "hardware/gpio.h"
#include "hardware/spi.h"

#include "mipi_dbi.h"

// printf
#include <stdio.h>

#define USE_DMA 1

#define DBI_LOG
#define DBI_TIME_SPI 0

static uint dma_channels[2] = { ~0, ~0 };

/*
 * Many controllers have a max speed of 10MHz, but can be pushed way beyond
 * that. Increase reliability by running pixel data at max speed and the rest
 * at 10MHz, preventing transfer glitches from messing up the init settings.
 */

void mipi_dbi_command_buf(const struct mipi_dbi *dbi, uint8_t cmd, const uint8_t *data, size_t len)
{
    DBI_LOG("DCS: %02x", cmd);
    for (uint8_t i = 0; i < (len > 64 ? 64 : len); i++)
        DBI_LOG(" %02x", data[i]);
    DBI_LOG("\n");

    spi_set_format(dbi->spi, 8, dbi->cpol, dbi->cpha, SPI_MSB_FIRST);

    if (dbi->baudrate > 10000000)
        spi_set_baudrate(dbi->spi, 10000000);

    gpio_put(dbi->cs, 0);

    gpio_put(dbi->dc, 0);
    spi_write_blocking(dbi->spi, &cmd, 1);

    if (len) {
        gpio_put(dbi->dc, 1);
        spi_write_blocking(dbi->spi, data, len);
    }

    gpio_put(dbi->cs, 1);
}

void mipi_dbi_set_window(const struct mipi_dbi *dbi,
                         uint16_t x, uint16_t y,
                         uint16_t width, uint16_t height)
{
    uint16_t xe = x + width - 1;
    uint16_t ye = y + height - 1;

    mipi_dbi_command(dbi, MIPI_DCS_SET_COLUMN_ADDRESS,
                     x >> 8, x & 0xff, xe >> 8, xe & 0xff);
    mipi_dbi_command(dbi, MIPI_DCS_SET_PAGE_ADDRESS,
                     y >> 8, y & 0xff, ye >> 8, ye & 0xff);
}

static void mipi_dbi_update16_dma(const struct mipi_dbi *dbi, uint16_t x, uint16_t y,
                                  uint16_t width, uint16_t height, void *buf, size_t len)
{
    uint idx = spi_get_index(dbi->spi);
    uint dma_channel = dma_channels[idx];

    if (dma_channel == ~0) {
        dma_channel = dma_claim_unused_channel(true);
        dma_channel_config config = dma_channel_get_default_config(dma_channel);
        channel_config_set_transfer_data_size(&config, DMA_SIZE_16);
        channel_config_set_dreq(&config, idx ? DREQ_SPI1_TX : DREQ_SPI0_TX);
        dma_channel_configure(dma_channel, &config, &spi_get_hw(dbi->spi)->dr, buf, width * height, false);

//    dma_channel_set_read_addr(dma_channel, framebuffer, false);
//    dma_channel_set_write_addr(dma_channel, &spi_get_hw(dbi.spi)->dr, false);
//    dma_channel_set_trans_count(dma_channel, transfer_count, false);
//    dma_channel_set_config(dma_channel, &config, false);

        dma_channels[idx] = dma_channel;
    }

    if (dma_channel_is_busy(dma_channel))
        DBI_LOG("Waiting for DMA to finish\n");

    dma_channel_wait_for_finish_blocking(dma_channel);

    mipi_dbi_set_window(dbi, x, y, width, height);

    gpio_put(dbi->cs, 0);

    gpio_put(dbi->dc, 0);
    uint8_t cmd = MIPI_DCS_WRITE_MEMORY_START;
    spi_write_blocking(dbi->spi, &cmd, 1);

    gpio_put(dbi->dc, 1);

    spi_set_format(dbi->spi, 16, dbi->cpol, dbi->cpha, SPI_MSB_FIRST);
    spi_set_baudrate(dbi->spi, dbi->baudrate);

    uint64_t start = time_us_64();

    dma_channel_set_read_addr(dma_channel, buf, false);
    dma_channel_set_trans_count(dma_channel, width * height, true);

    if (DBI_TIME_SPI) {
        dma_channel_wait_for_finish_blocking(dma_channel);
        printf("dma=%llu us\n", time_us_64() - start);
    }
}

void mipi_dbi_update16(const struct mipi_dbi *dbi, uint16_t x, uint16_t y,
                       uint16_t width, uint16_t height, void *buf, size_t len)
{
    if (USE_DMA) {
        mipi_dbi_update16_dma(dbi, x, y, width, height, buf, len);
        return;
    }

    mipi_dbi_set_window(dbi, x, y, width, height);

    gpio_put(dbi->cs, 0);

    gpio_put(dbi->dc, 0);
    uint8_t cmd = MIPI_DCS_WRITE_MEMORY_START;
    spi_write_blocking(dbi->spi, &cmd, 1);

    gpio_put(dbi->dc, 1);

    spi_set_format(dbi->spi, 16, dbi->cpol, dbi->cpha, SPI_MSB_FIRST);
    spi_set_baudrate(dbi->spi, dbi->baudrate);

    uint64_t start = time_us_64();

    spi_write16_blocking(dbi->spi, buf, len / 2);

    if (DBI_TIME_SPI)
        printf("write=%llu us\n", time_us_64() - start);

    gpio_put(dbi->cs, 1);
}

void mipi_dbi_spi_init(const struct mipi_dbi *dbi)
{
    spi_init(dbi->spi, dbi->baudrate);

    gpio_set_function(dbi->sck,  GPIO_FUNC_SPI);
    gpio_set_function(dbi->mosi, GPIO_FUNC_SPI);

    gpio_set_function(dbi->cs, GPIO_FUNC_SIO);
    gpio_set_dir(dbi->cs, GPIO_OUT);

    gpio_set_function(dbi->dc, GPIO_FUNC_SIO);
    gpio_set_dir(dbi->dc, GPIO_OUT);
}
