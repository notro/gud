import argparse
import os
import statistics
import sys
from time import sleep
from gud import *

TEST_MODES = ((1920, 1080), (1024, 768), (800, 600), (640, 480))

def states(dev, preferred_mode, fmt):
    connectors = [connector for connector in dev.connectors if connector.connected]
    if not connectors:
        return
    connector = connectors[0]

    # only use test modes and filter out similar sizes
    modes = {}
    for mode in connector.modes:
        size = (mode.hdisplay, mode.vdisplay)
        if (mode.hdisplay, mode.vdisplay) in TEST_MODES and not size in modes:
            modes[size] = mode

    if preferred_mode:
        modes = [mode for mode in connector.modes if mode.flags & GUD_DISPLAY_MODE_FLAG_PREFERRED]
        if not modes:
            modes = (connector.modes[0], )
    elif modes:
        modes = modes.values()
    else:
        modes = connector.modes

    if fmt:
        formats = (fmt, )
    else:
        formats = dev.formats

    for fmt in formats:
        if len(formats) > 1 and fmt == GUD_PIXEL_FORMAT_ARGB8888 and GUD_PIXEL_FORMAT_XRGB8888 in dev.formats:
            continue
        for mode in modes:
            yield State(dev, mode, fmt, connector)


def test_all_rgb(dev, state, speed):
    if state.format < GUD_PIXEL_FORMAT_XRGB1111:
        return
    print('  RGB')
    img = Image(dev, state.format, state.mode)
    for index, (color, name) in enumerate((('#c00000', 'RED'), ('#00c000', 'GREEN'), ('#0000c0', 'BLUE'))):
        img.text(name, y = index * img.height / 3, color=color, fraction=0.3)
    img.flush(compress=False)
    sleep(1 * speed)

def double_border(dev, state, msg):
    img = Image(dev, state.format, state.mode)
    img.rectangle(0, 0, img.width, img.height, outline='white')
    img.rectangle(2, 2, img.width - 4, img.height - 4, outline='white')
    img.text(msg, fraction=0.4)
    img.flush(compress=False)

def test_all_border(dev, state, speed):
    print('  Double border')
    double_border(dev, state, 'Double border 1 pixel gap')
    sleep(2 * speed)

def test_all_grid(dev, state, speed):
    print('  Grid test:', end='', flush=True)
    if state.format < GUD_PIXEL_FORMAT_XRGB1111:
        colors = ('#000000', )
    else:
        colors = ('#c00000', '#00c000', '#0000c0')

    grid = Image(dev, state.format, state.mode)

    num_width = 8
    w = grid.width // num_width
    num_height = grid.height // w

    for y in range(num_height):
        for x in range(num_width):
            grid.rectangle(x * w, y * w, w, w, fill=colors[x % len(colors)], outline='white')
    grid.flush()
    sleep(0.5 * speed)

    dot_w = w // 2
    dot_off = (w - dot_w) // 2
    for y in range(num_height):
        for x in range(num_width):
            print('.', end='', flush=True)
            grid.rectangle(x * w, y * w, w, w, fill='#000000')
            grid.rectangle(x * w + dot_off, y * w + dot_off, dot_w, dot_w, fill=colors[x % len(colors)])
            grid.flush(x * w, y * w, w, w)
    print()

def test_one_rotation(dev, state, speed):
    if not dev.properties or dev.properties[0].prop != GUD_PROPERTY_ROTATION:
        return
    print('  Plane rotation:', end='', flush=True)
    prop = dev.properties[0]
    for rotation in (GUD_ROTATION_90, GUD_ROTATION_180, GUD_ROTATION_270, GUD_ROTATION_0):
        for reflect in (0, ): # How is this supposed to work? (GUD_ROTATION_REFLECT_X, GUD_ROTATION_REFLECT_Y, 0):
            val = rotation | reflect
            if val & prop.mask:
                print(f' {rotation_to_str(val)}', end='', flush=True)
                double_border(dev, state, f'Rotation {rotation_to_str(val)}')
                dev.set(prop.prop, val)
                dev.commit(state)
                sleep(3 * speed)
    print()

def test_one_margins(dev, state, speed):
    margins = [prop for prop in state.connector.properties if prop.prop in (GUD_PROPERTY_TV_LEFT_MARGIN, GUD_PROPERTY_TV_RIGHT_MARGIN, GUD_PROPERTY_TV_TOP_MARGIN, GUD_PROPERTY_TV_BOTTOM_MARGIN)]
    if not margins:
        return
    print('  Connector margins:')
    for prop in margins:
        print(f'    {property_to_str(prop.prop)}:', end='', flush=True)
        for val in range(100, -1, -20):
            state.connector.set(prop.prop, val)
            print(f' {val}', end='', flush=True)
            double_border(dev, state, f'{property_to_str(prop.prop)} = {val}')
            dev.commit(state)
            sleep(1 * speed)
        print()
    print(f'    ALL:', end='', flush=True)
    for val in range(100, -1, -25):
        print(f' {val}', end='', flush=True)
        for prop in margins:
            state.connector.set(prop.prop, val)
        double_border(dev, state, f'ALL = {val}')
        dev.commit(state)
        sleep(1 * speed)
    print()


def main(args):
    fmt = None
    if args.format:
        fmt = name_to_format(args.format)
        if fmt is None:
            print(f'Format not recognized: {args.format}')
            return

    gud = find_first_setup()
    gud.controller_enable()

    test_all = [globals()[method] for method in globals() if method.startswith('test_all_') and method[9:] in args.tests]
    if test_all:
        for state in states(gud, args.preferred_mode, fmt):
            print(state)
            gud.commit(state)

            # Show mode and format
            img = Image(gud, state.format, state.mode)
            img.text(str(state), fraction=0.5)
            img.flush(compress=False)
            sleep(3 * args.speed)

            for test in test_all:
                test(gud, state, args.speed)

    test_one = [globals()[method] for method in globals() if method.startswith('test_one_') and method[9:] in args.tests]
    if test_one:
        state = State(gud)
        print(state)
        gud.commit(state)
        sleep(3 * args.speed)
        for test in test_one:
            test(gud, state, args.speed)

    if not args.keep:
        gud.disable()
        gud.controller_disable()


if __name__ == '__main__':
    tests = [method[9:] for method in globals().keys() if method.startswith('test_')]
    modes = ' '.join([f'{mode[0]}x{mode[1]}' for mode in TEST_MODES])

    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter,
        description=f'''
GUD visual tester

By default runs visual tests on:
- the first connected connector
- all formats (except ARGB8888 if XRGB8888 is supported)
- all modes covered by {modes} (if not use all modes)

Some tests run only once on the default mode and format.
''')
    parser.add_argument('tests', nargs='*', default=tests, help=f'Tests: {" ".join(tests)}')
    parser.add_argument('-s', '--speed', type=float, default=1.0, help='How fast to run the tests (default=1.0)')
    parser.add_argument('-k', '--keep', action='store_true', help="Don't disable display before exiting")
    parser.add_argument('-p', '--preferred-mode', action='store_true', help='Only use the preferred mode')
    parser.add_argument('-f', '--format', help='Only use the specified format (ARGB8888, XRGB8888, RGB565, XRGB1111, R1)')
    args = parser.parse_args()

    if not set(args.tests).issubset(tests):
        print('Unknown tests:', ' '.join(set(args.tests) - set(tests)))
        sys.exit(1)

    main(args)
