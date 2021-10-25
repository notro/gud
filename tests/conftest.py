# SPDX-License-Identifier: CC0-1.0

import pytest

import mmap
import os
import os.path
import sys
import termios
import time
import tty

import numpy
import pykms
from PIL import Image as PIL_Image
from PIL import ImageDraw as PIL_ImageDraw
from PIL import ImageFont as PIL_ImageFont


def pytest_sessionstart(session):
    pytest.gud = Display(xrgb8888_format=session.config.getoption('--xrgb8888'))


def pytest_addoption(parser):
    parser.addoption('--xrgb8888', help='XRGB8888 emulated format', choices=('R1', 'R8', 'XRGB1111', 'RGB332', 'RGB565', 'RGB888'))
    parser.addoption('--test-delay', type=int, default=5, help='Delay between tests (default 5 secs)')


def pytest_configure(config):
    config.test_delay = config.getoption('--test-delay')
    if config.test_delay < 0:
        config.test_delay = 0

# https://stackoverflow.com/questions/42760059/how-to-make-pytest-wait-for-manual-user-action

def getc():
    fd = sys.stdin.fileno()
    attrs = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd)
        return os.read(fd, 4)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, attrs)


@pytest.fixture(autouse=True)
def test_delay(pytestconfig):
    yield
    if sys.stdin.isatty(): # enable using cmdline option: -s
        c = getc()
        if c in [b'q', b'Q']:
            pytest.exit('User exit', 1)
    else:
        time.sleep(pytestconfig.test_delay)


@pytest.fixture(scope='module')
def display(pytestconfig):
    if not pytest.gud:
        pytest.gud = Display(xrgb8888_format=pytestconfig.getoption('--xrgb8888'))
    return pytest.gud


# Release DRM device so others can become master
@pytest.fixture(scope='module')
def nodisplay():
    pytest.gud = None


class Connector:
    def __init__(self, display, connector):
        self.display = display
        self.base = connector
        basename = os.path.basename(self.display.path)
        self.bl_path = f'/sys/class/drm/{basename}-{self.base.fullname}/{basename}-{self.base.fullname}-backlight/brightness'
        self.has_brightness = os.path.exists(self.bl_path)
        self.access_brightness = os.access(self.bl_path, os.W_OK)

    @property
    def modes(self):
        return self.base.get_modes()

    @property
    def properties(self):
        ids =self.base.prop_map.keys()
        return [prop for prop in self.display.card.properties if prop.id in ids]

    @property
    def brightness(self):
        if not self.has_brightness:
            return None
        with open(self.bl_path, 'r') as f:
            val = f.read()
        return int(val)

    @brightness.setter
    def brightness(self, val):
        if not self.access_brightness:
            raise ValueError('no brightness')
        with open(self.bl_path, 'r+') as f:
            f.write(str(val))


TEST_MODES = ((1920, 1080), (1024, 768), (800, 600), (640, 480))

class Display:
    def __init__(self, index=0, connector='', xrgb8888_format=None):
        self.card = pykms.Card('gud', index)
        self.path = os.readlink(f'/proc/self/fd/{self.card.fd}')
        self.res = pykms.ResourceManager(self.card)
        self.connector = Connector(self, self.res.reserve_connector(connector))
        self.crtc = self.res.reserve_crtc(self.connector.base)
        self.plane = self.res.reserve_generic_plane(self.crtc)
        self.xrgb8888_format = xrgb8888_format
        self.enabled = True

    @property
    def formats(self):
        formats = self.plane.formats
        if self.xrgb8888_format and self.xrgb8888_format not in ('R1', 'R8', 'XRGB1111'):
            formats.remove(pykms.PixelFormat.XRGB8888)
        return formats

    @property
    def rotation(self):
        return next((prop for prop in self.card.properties if prop.name == 'rotation'), None)

    @property
    def rotation_values(self):
        if self.rotation:
            return self.rotation.enums.values()
        return []

    def test_modes(self):
        modes = self.connector.modes
        if len(modes) <= len(TEST_MODES):
            return modes
        # trim down: use only TEST_MODES modes and filter out similar sizes
        tmodes = {}
        for mode in modes:
            size = (mode.hdisplay, mode.vdisplay)
            if size in TEST_MODES and not size in tmodes:
                tmodes[size] = mode
        return tmodes.values()

    def image(self, mode, fmt=pykms.PixelFormat.XRGB8888):
        return Image(self, mode, fmt)

    # keep=True: Prevent gc when test variable goes out of scope which will disable the pipeline
    #            This keeps the display on during test_delay fixture teardown
    def state(self, keep=False):
        state = State(self, self.connector)
        self._state = state if keep else None
        return state


class State:
    def __init__(self, display, connector):
        self.display = display
        self.connector = connector
        self.fb = None
        self.mode = None

        self.card = self.display.card
        self.crtc = self.card.crtcs[0]
        self.plane = self.card.planes[0]

        self.properties = []

    def clear(self):
        self.properties = []

    def add(self, obj, prop, val):
        kobj = getattr(obj, 'base', obj)
        self.properties.append((kobj, prop, val))

    def _commit(self, req):
        ret = req.commit_sync(allow_modeset = True)
        if ret < 0:
            raise OSError(-ret, os.strerror(-ret))

    def disable(self):
        req = pykms.AtomicReq(self.card)
        req.add(self.crtc, {'ACTIVE': 0, 'MODE_ID': 0})
        self._commit(req)

    def commit(self):
        mode_blob = self.mode.to_blob(self.card)

        req = pykms.AtomicReq(self.card)
        req.add_connector(self.connector.base, self.crtc)
        req.add(self.crtc, {'ACTIVE': int(self.display.enabled), 'MODE_ID': mode_blob.id})
        req.add_plane(self.plane, self.fb, self.crtc)

        for prop in self.properties:
            req.add(prop[0], prop[1], prop[2])

        self._commit(req)


class Image:
    def __init__(self, display, mode, fmt=pykms.PixelFormat.XRGB8888):
        if fmt == pykms.PixelFormat.XRGB8888:
            imgmode = 'RGBX'
        elif fmt in (pykms.PixelFormat.RGB888, pykms.PixelFormat.RGB565, pykms.PixelFormat.RGB332):
            imgmode = 'RGB'
        elif int(fmt) == 0x20203852: # R8 is not supported by pykms
            fmt = pykms.PixelFormat.XRGB8888
            imgmode = 'RGBX'
        else:
            raise ValueError(f'Format not supported: {fmt} : {hex(int(fmt))}')
        self.format = fmt
        bgcolor = 0
        self.display = display
        self.width, self.height = mode.hdisplay, mode.vdisplay
        self.fb = pykms.DumbFramebuffer(display.card, self.width, self.height, fmt)
        self.map = mmap.mmap(self.fb.fd(0), self.fb.size(0))
        self.image = PIL_Image.new(imgmode, (self.width, self.height), bgcolor)
        self.draw = PIL_ImageDraw.Draw(self.image)

    def clear(self):
        self.rect(0, 0, self.width, self.height, fill=0)

    def rect(self, x, y, width, height, fill=None, outline=None):
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
                font = PIL_ImageFont.truetype("FreeMono", size)
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

    def test(self):
        if self.display.xrgb8888_format in ('R1',):
            monochrome_image(self)
        elif self.display.xrgb8888_format == 'XRGB1111':
            xrgb1111_image(self)
        else:
            smpte_image(self)

    def write(self):
        if self.format == pykms.PixelFormat.XRGB8888:
            buf = self.image.tobytes('raw', 'BGRX')
        elif self.format == pykms.PixelFormat.RGB888:
            buf = self.image.tobytes('raw', 'BGR')
        elif self.format == pykms.PixelFormat.RGB565:
            # https://helperbyte.com/questions/180384/than-to-convert-a-picture-in-format-bmp565-in-python
            rgb888 = numpy.asarray(self.image)
            assert rgb888.shape[-1] == 3 and rgb888.dtype == numpy.uint8

            # If partial writes are needed:
            # rgb888 = rgb888[y1 : y1 + height, x1 : x1 + width]

            r5 = (rgb888[..., 0] >> 3 & 0x1f).astype(numpy.uint16)
            g6 = (rgb888[..., 1] >> 2 & 0x3f).astype(numpy.uint16)
            b5 = (rgb888[..., 2] >> 3 & 0x1f).astype(numpy.uint16)
            rgb565 = r5 << 11 | g6 << 5 | b5
            buf = bytes(rgb565)
        elif self.format == pykms.PixelFormat.RGB332:
            rgb888 = numpy.asarray(self.image)
            assert rgb888.shape[-1] == 3 and rgb888.dtype == numpy.uint8
            r3 = (rgb888[..., 0] >> 5).astype(numpy.uint8)
            g3 = (rgb888[..., 1] >> 5).astype(numpy.uint8)
            b2 = (rgb888[..., 2] >> 6).astype(numpy.uint8)
            rgb332 = r3 << 5 | g3 << 2 | b2
            buf = bytes(rgb332)

        self.map.seek(0)
        self.map.write(buf)

    def flush(self, *args):
        self.write()
        self.fb.flush(*args)


def draw_smpte_rects(img, x, y, width, height, colors):
    for i in range(len(colors)):
        img.rect(x + (width * i), y, x + (width * (i + 1)), y + height, fill=colors[i], outline=colors[i])


def smpte_image(img):
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

    # border to show framebuffer boundaries
    img.rect(0, 0, img.width, img.height, outline='white')


def xrgb1111_image(img):
    # top colors: white, yellow, cyan, green, magenta, red, blue
    width = img.width // 7
    height = img.height * 6 // 9
    draw_smpte_rects(img, 0, 0, width, height, ['#ffffff', '#ffff00', '#00ffff', '#00ff00', '#ff00ff', '#ff0000', '#0000ff'])

    # bottom colors: red, green, blue, black
    y = height
    width = img.width / 4
    height = img.height * 3 / 9
    draw_smpte_rects(img, 0, y, width, height, ['#ff0000', '#00ff00', '#0000ff', '#000000'])

    # border to show framebuffer boundaries
    img.rect(0, 0, img.width, img.height, outline='white')


def monochrome_image(img):
    colors = ('#FFFFFF', '#000000')
    num_width = 8
    w = img.width // num_width
    num_height = img.height // w

    for y in range(num_height):
        for x in range(num_width):
            img.rect(x * w, y * w, w, w, fill=colors[(x + y) % len(colors)])
