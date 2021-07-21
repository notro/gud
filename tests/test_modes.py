# SPDX-License-Identifier: CC0-1.0

import pytest
import time
import pykms

def pytest_generate_tests(metafunc):
    # pytest parametrize runs each test through all parameters before moving on to the next test
    # at least vc4 (rPi) has slow modesetting so this makes sure that tests are run sequentially using the same display mode
    modes = pytest.gud.test_modes()
    metafunc.parametrize('mode', modes, ids=[f'{mode.hdisplay}x{mode.vdisplay}' for mode in modes], scope='class')

@pytest.fixture(scope='class')
def state():
    return pytest.gud.state()

@pytest.mark.parametrize('format', pytest.gud.formats, ids=[fmt.name for fmt in pytest.gud.formats])
class TestModes:
    def test_smpte(self, state, mode, format):
        fb = state.fb # keep fb from being destroyed before commit (which disables the pipeline)
        image = state.display.image(mode, format)
        state.mode = mode
        state.fb = image.fb

        image.test()
        image.text(state.mode.to_string_short() + ' ' + format.name, y = image.height / 3, fraction=0.5)
        image.write()
        state.commit()

    def test_grid(self, state, mode, format):
        fb = state.fb # keep fb from being destroyed before commit (which disables the pipeline)
        image = state.display.image(mode, format)
        state.mode = mode
        state.fb = image.fb
        state.commit()

        if state.display.xrgb8888_format in ('R1',):
            colors = ('#000000', )
        else:
            colors = ('#c00000', '#00c000', '#0000c0')

        num_width = 8
        w = image.width // num_width
        num_height = image.height // w

        for y in range(num_height):
            for x in range(num_width):
                image.rect(x * w, y * w, w, w, fill=colors[x % len(colors)], outline='white')
        image.flush()
        time.sleep(0.5)

        dot_w = w // 2
        dot_off = (w - dot_w) // 2
        for y in range(num_height):
            for x in range(num_width):
                print('.', end='', flush=True)
                image.rect(x * w, y * w, w, w, fill='#000000')
                image.rect(x * w + dot_off, y * w + dot_off, dot_w, dot_w, fill=colors[x % len(colors)])
                image.flush(x * w, y * w, w, w)
                time.sleep(0.5)
