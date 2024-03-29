# SPDX-License-Identifier: CC0-1.0

import os
import struct
from timeit import default_timer as timer
import lz4
import lz4.block
import numpy
from PIL import Image as PIL_Image
from PIL import ImageDraw as PIL_ImageDraw
from PIL import ImageFont
from .gud_h import *


class Image(object):
    def __init__(self, dev, fmt, mode, color=0):
        self.dev = dev
        self.format = fmt
        self.mode = mode
        self.width = mode.hdisplay
        self.height = mode.vdisplay
        self._cache = {}

        if fmt == GUD_PIXEL_FORMAT_RGB565:
            self.cpp = 2
        elif fmt in (GUD_PIXEL_FORMAT_XRGB8888, GUD_PIXEL_FORMAT_ARGB8888):
            self.cpp = 4
        elif fmt in (GUD_PIXEL_FORMAT_XRGB1111, GUD_PIXEL_FORMAT_R1):
            self.cpp = 0
        else:
            raise ValueError(f'Format 0x{fmt:02x} is not supported')
        self.pitch = self.width * self.cpp

        self.image = PIL_Image.new('RGB', (self.width, self.height), color)
        self.draw = PIL_ImageDraw.Draw(self.image)

    def rectangle(self, x, y, width, height, fill=None, outline=None):
        #print('rectangle:', x, y, width, height)

        # Pillow docs say: The second point is just outside the drawn rectangle.
        # What I see: The second point is just inside the drawn rectangle.
        # https://stackoverflow.com/questions/58792202/the-coordinate-system-of-pillow-seems-to-be-different-for-the-draw-section
        self.draw.rectangle([(x, y), (x + width - 1, y + height - 1)], fill=fill, outline=outline)

    def text(self, text, x=None, y=None, color=None, fraction=None):
        font = None
        if fraction:
            size = 16
            step = 16
            while step > 1:
                font = ImageFont.truetype("FreeMono", size)
                w, h = font.getsize(text)
                #print('step, w, h:', step, w, h)
                if w < fraction * self.width:
                    size += step
                else:
                    size -= step // 2
                    step //= 4
            #print('size', size)
        else:
            w, h = self.draw.textsize(text)
        if x is None:
            x = (self.width - w) / 2
        if y is None:
            y = (self.height - h) / 2
        self.draw.text((x, y), text, font=font, fill=color)

    def random(self, ratio=0):
        if self.format in (GUD_PIXEL_FORMAT_R1, GUD_PIXEL_FORMAT_XRGB1111):
            # The resulting ratio will not be as precise
            rand_lines = self.height // (ratio if ratio else 1)
            zero_lines = self.height - rand_lines
            zeroes = self.width * 3 * zero_lines
            buf = bytes(zeroes) + bytes(os.urandom(self.width * 3 * rand_lines))
            self.image.frombytes(buf, 'raw', 'RGB')
            return

        length = self.width * self.height * self.cpp
        if ratio == 0:
            buf = bytes(os.urandom(length))
        else:
            if self.cpp == 4:
                rand_lines = self.height // ratio
                zeroes = self.width * (self.height - rand_lines) * 4
                xrgb8888 = numpy.random.randint(0, 0xFFFFFF00, (self.width, rand_lines), dtype=numpy.uint32)
                buf = bytearray(zeroes) + bytearray(xrgb8888)
            else:
                zeroes = length - (length // ratio)
                buf = bytearray(zeroes) + bytearray(os.urandom(length - zeroes))

            assert len(buf) == length

            #self.image.frombytes(bytes(buf), 'raw', 'RGB;16')
            #self.text('Compress', y=200)
            #buf = self.data(0, 0, self.width, self.height)

            want = len(buf) // ratio
            i = zeroes
            while i < length:
                compressed = lz4.block.compress(buf, return_bytearray=True, store_size=False)
                if len(compressed) <= want:
                    #print(f'random: ratio={ratio} i={i} zeroes={zeroes} length-(length/ratio)={length-(length/ratio)} length/i={length/i} length/(length - i)={length/(length - i)}')
                    break
                stride = (len(compressed) - want + 1) // 2
                if not stride:
                    stride = 1
                #print(f':: i={i} stride={stride} {len(compressed) - want} ', end='', flush=True)
                buf[i : i + stride] = bytearray(stride) # Zeros
                i += stride
            buf = bytes(buf)

        #print('non zero count:', length - buf.count(b'\x00'))

        if self.format == GUD_PIXEL_FORMAT_RGB565:
            self.image.frombytes(buf, 'raw', 'RGB;16')
        elif self.format in (GUD_PIXEL_FORMAT_XRGB8888, GUD_PIXEL_FORMAT_ARGB8888):
            self.image.frombytes(buf, 'raw', 'BGRX')
        else:
            raise ValueError('format not supported')

    def data(self, x1, y1, width, height):
        if self.format in (GUD_PIXEL_FORMAT_XRGB8888, GUD_PIXEL_FORMAT_ARGB8888) and width == self.width:
            # BGRX is little endian form of XRGB
            buf = self.image.tobytes('raw', 'BGRX')
            #print('len:', len(buf))
            offset = y1 * self.pitch
            buf = buf[offset : offset + height * self.pitch]
            #print('len:', len(buf))
            return bytearray(buf)

        # PIL doesn't have native RGB -> RGB565 conversion
        # https://github.com/python-pillow/Pillow/blob/master/src/libImaging/Pack.c
        if self.format == GUD_PIXEL_FORMAT_RGB565:
            import numpy
            # https://helperbyte.com/questions/180384/than-to-convert-a-picture-in-format-bmp565-in-python
            rgb888 = numpy.asarray(self.image)
            assert rgb888.shape[-1] == 3 and rgb888.dtype == numpy.uint8

            rgb888 = rgb888[y1 : y1 + height, x1 : x1 + width]

            r5 = (rgb888[..., 0] >> 3 & 0x1f).astype(numpy.uint16)
            g6 = (rgb888[..., 1] >> 2 & 0x3f).astype(numpy.uint16)
            b5 = (rgb888[..., 2] >> 3 & 0x1f).astype(numpy.uint16)
            rgb565 = r5 << 11 | g6 << 5 | b5
            buf = bytearray(rgb565)
            #print('len(buf):', len(buf))
            return buf

        val = None
        data = bytearray()
        #print('data(', x1, y1, width, height, ')')
        for y in range(y1, y1 + height):
            for x in range(x1, x1 + width):
                #print(x,y)
                pix = self.image.getpixel((x, y))
                if self.format == GUD_PIXEL_FORMAT_R1:
                    pixpos = x % 8 # within byte from the left
                    pixshift = 8 - pixpos - 1

                    if x % 8 == 0:
                        val = 0

                    r = pix[0] & 0xFF
                    g = pix[1] & 0xFF
                    b = pix[2] & 0xFF
                    # ITU BT.601: Y = 0.299 R + 0.587 G + 0.114 B
                    gray8 = (3 * r + 6 * g + b) // 10;
                    val |= (gray8 & 1) << pixshift

                    if x % 8 == 7:
                        data.append(val)
                        val = None
                elif self.format == GUD_PIXEL_FORMAT_XRGB1111:
                    pixpos = x % 2 # within byte from the left
                    pixshift = (2 - pixpos - 1) * 4;

                    if x % 2 == 0:
                        val = 0

                    r = (pix[0] >> 7) & 0x01
                    g = (pix[1] >> 7) & 0x01
                    b = (pix[2] >> 7) & 0x01
                    xrgb1111 = (r << 2) | (g << 1) | b
                    val |= xrgb1111 << pixshift

                    if x % 2 == 1:
                        data.append(val)
                        val = None
                elif self.format == GUD_PIXEL_FORMAT_RGB565:
                    r = (pix[0] >> 3) & 0x1F
                    g = (pix[1] >> 2) & 0x3F
                    b = (pix[2] >> 3) & 0x1F
                    data.extend(struct.pack('H', (r << 11) | (g << 5) | b))
                elif self.format in (GUD_PIXEL_FORMAT_XRGB8888, GUD_PIXEL_FORMAT_ARGB8888):
                    r = pix[0] & 0xFF
                    g = pix[1] & 0xFF
                    b = pix[2] & 0xFF
                    data.extend(struct.pack('I', (r << 16) | (g << 8) | b))
                else:
                    raise ValueError('format not supported')

            # R1 or XRGB1111: In case width isn't a pixels per byte multiple
            if val is not None:
                data.append(val)
                val = None

        return data

    def flush(self, x=0, y=0, width=None, height=None, compress=True, use_cached=False):
        if self.dev.descriptor.flags & GUD_DISPLAY_FLAG_FULL_UPDATE:
            x = 0
            y = 0
            width = self.width
            height = self.height
        elif width is None or height is None:
            width = self.width
            height = self.height
        #else:
        #    print(f'flush({x}, {y}, {width}, {height})')

        # Align to byte boundary
        if self.format == GUD_PIXEL_FORMAT_R1:
            adj = x % 8
            x -= adj
            width += adj
        elif self.format == GUD_PIXEL_FORMAT_XRGB1111:
            adj = x % 2
            x -= adj
            width += adj

        lines = height
        if self.dev.max_buffer_size < lines * self.pitch:
            lines = self.dev.max_buffer_size // self.pitch

        start = timer()

        parts = (height + lines - 1) // lines
        for i in range(parts):
            self._flush(i, x, y + (i * lines), width, min(lines, height), compress, use_cached)
            height -= lines

        return timer() - start, parts

    def _flush(self, i, x, y, width, height, compress, use_cached):
        if use_cached:
            buf = self._cache[i]
        else:
            buf = self.data(x, y, width, height)
            self._cache[i] = buf

        if not self.dev.descriptor.flags & GUD_DISPLAY_FLAG_FULL_UPDATE:
            req = gud_drm_req_set_buffer()
            req.x = x
            req.y = y
            req.width = width
            req.height = height
            req.length = len(buf)
            req.compression = 0
            req.compressed_length = 0

            if compress and self.dev.descriptor.compression & GUD_COMPRESSION_LZ4:
                compressed = lz4.block.compress(buf, return_bytearray=True, store_size=False)
                if (len(compressed) <= len(buf)):
                    buf = compressed
                    req.compression = GUD_COMPRESSION_LZ4
                    req.compressed_length = len(compressed)

            self.dev.req_set_buffer(req)

        self.dev.bulk_write(buf, len(buf))

    def __str__(self):
        return f'{self.mode.hdisplay}x{self.mode.vdisplay} {format_to_name(self.format)}'


def draw_smpte_rects(img, x, y, width, height, colors):
    for i in range(len(colors)):
        img.rectangle(x + (width * i), y, x + (width * (i + 1)), y + height, fill=colors[i], outline=colors[i])

def draw_smpte_pattern(img):
    #print('draw_smpte_pattern', img.width, img.height)

    # top colors: grey/silver, yellow, cyan, green, magenta, red, blue
    y = 0
    width = img.width // 7
    height = img.height * 6 // 9
    draw_smpte_rects(img, 0, 0, width, height, ['#c0c0c0', '#c0c000', '#00c0c0', '#00c000', '#c000c0', '#c00000', '#0000c0'])

    # middle colors: blue, black magenta, black, cyan, black, grey
    y = height
    width = img.width / 7
    height = img.height * 1 / 9
    draw_smpte_rects(img, 0, y, width, height, ['#0000c0', '#131313', '#c000c0', '#131313', '#00c0c0', '#131313', '#c0c0c0'])

    # bottom colors: in-phase, super white, quadrature, black, 3.5%, 7.5%, 11.5%, black
    y += height
    width = img.width / 6
    height = img.height * 2 / 9
    draw_smpte_rects(img, 0, y, width, height, ['#00214c', '#ffffff', '#32006a', '#131313'])

    x = width * 4
    width = img.width / 6 / 3
    draw_smpte_rects(img, x, y, width, height, ['#090909', '#131313', '#1d1d1d'])

    x = img.width * 5 / 6
    width = img.width / 6
    draw_smpte_rects(img, x, y, width, height, ['#131313'])

def smpte_image(dev, fmt, mode, text=None):
    img = Image(dev, fmt, mode)
    draw_smpte_pattern(img)
    if text:
        img.text(text, y = img.height / 3)
    return img


def checkerboard_image(dev, fmt, mode):
    colors = ('#FFFFFF', '#000000')
    img = Image(dev, fmt, mode)
    num_width = 8
    w = img.width // num_width
    num_height = img.height // w

    for y in range(num_height):
        for x in range(num_width):
            img.rectangle(x * w, y * w, w, w, fill=colors[(x + y) % len(colors)])
    return img
