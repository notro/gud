# SPDX-License-Identifier: CC0-1.0

import pytest
import pykms
import time

@pytest.fixture(scope='class')
def state():
    display = pytest.gud
    state = display.state()
    state.mode = display.connector.modes[0]
    state.image = display.image(state.mode)
    state.fb = state.image.fb
    state.commit()
    return state

class TestProperties:
    @pytest.mark.skipif(not pytest.gud.rotation, reason='no rotation support')
    @pytest.mark.parametrize('reflection', [v for v in pytest.gud.rotation_values if 'reflect' in v] + ['reflect-none'])
    @pytest.mark.parametrize('rotation', [v for v in pytest.gud.rotation_values if 'rotate' in v and v != 'rotate-0'] + ['rotate-0'])
    def test_rotation(self, state, rotation, reflection):
        values = { 'rotate-0': pykms.Rotation.ROTATE_0,
                   'rotate-90': pykms.Rotation.ROTATE_90,
                   'rotate-180': pykms.Rotation.ROTATE_180,
                   'rotate-270': pykms.Rotation.ROTATE_270,
                   'reflect-none': 0,
                   'reflect-x': pykms.Rotation.REFLECT_X,
                   'reflect-y': pykms.Rotation.REFLECT_Y,
                 }

        image = state.image

        image.rect(0, 0, image.width, image.height, fill=0, outline='white')
        image.text(' TOP ', y=8, color='white', fraction=0.1)
        image.text('LEFT', x=8, color='white', fraction=0.1)
        image.text(f'{reflection}+{rotation}', color='white', fraction=0.3)
        image.write()

        val = values[rotation] + values[reflection]
        state.add(state.plane, state.display.rotation, val)
        state.commit()

    @pytest.mark.skipif(not any(p for p in pytest.gud.connector.properties if 'margin' in p.name), reason='no margin properties')
    @pytest.mark.parametrize('val', range(100, -1, -20))
    @pytest.mark.parametrize('margin', [p for p in pytest.gud.connector.properties if 'margin' in p.name], ids=lambda p: getattr(p, 'name', 'nomargin'))
    def test_margins(self, state, margin, val):
        image = state.image

        image.rect(0, 0, image.width, image.height, fill=0, outline='white')
        image.text(f'{margin.name} = {val}', color='white', fraction=0.3)
        image.write()

        state.clear()
        state.add(state.connector, margin, val)
        state.commit()

    @pytest.mark.skipif(not any(p for p in pytest.gud.connector.properties if 'margin' in p.name), reason='no margin properties')
    @pytest.mark.parametrize('val', range(100, -1, -25))
    def test_margins_all(self, state, val):
        display = state.display
        image = state.image

        image.rect(0, 0, image.width, image.height, fill=0, outline='white')
        image.text(f'MARGINS = {val}', color='white', fraction=0.3)
        image.write()

        state.clear()
        margins = [p for p in display.connector.properties if 'margin' in p.name]
        for margin in margins:
            state.add(state.connector, margin, val)
        state.commit()

    @pytest.mark.skipif(not pytest.gud.connector.has_brightness, reason='no brightness property')
    @pytest.mark.skipif(not pytest.gud.connector.access_brightness, reason='no backlight write permission')
    def test_brightness(self, state):
        display = state.display
        image = state.image
        for val in list(range(100, -1, -5)) + list(range(0, 101, 5)):
            image.test()
            image.text(f'Brightness {val}', fraction=0.5)
            image.flush()
            display.connector.brightness = val
            time.sleep(0.1)
