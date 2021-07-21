#!/usr/bin/env python3

# SPDX-License-Identifier: CC0-1.0

import argparse
import os
import statistics
from time import sleep
from gud import *


def compression_ratio(dev, state, ratio, iterations):
    img = Image(dev, state.format, state.mode)
    length = img.random(ratio)
    elapsed = []
    for x in range(iterations):
        t, parts = img.flush(use_cached=x)
        elapsed.append(t)
    if iterations > 5:
        elapsed.pop(0) # Remove the outlier (includes PIL image conversion time)
    return min(elapsed), statistics.mean(elapsed), max(elapsed), parts

def no_compression(dev, state, iterations):
    if state.format < GUD_PIXEL_FORMAT_XRGB1111:
        img = checkerboard_image(dev, state.format, state.mode)
    else:
        img = smpte_image(dev, state.format, state.mode, text=str(state))
    elapsed = []
    for x in range(iterations):
        t, parts = img.flush(compress=False, use_cached=x)
        elapsed.append(t)
    if iterations > 5:
        elapsed.pop(0) # Remove the outlier (includes PIL image conversion time)
    return min(elapsed), statistics.mean(elapsed), max(elapsed), parts


def device_arg_split(arg):
    vid, pid = str(arg).split(':')
    return int(vid, 16), int(pid, 16)


def main(args):
    fmt = None
    if args.format:
        fmt = name_to_format(args.format)
        if fmt is None:
            print(f'Format not recognized: {args.format}')
            return

    if args.device:
        vid, pid = device_arg_split(args.device)
        gud = find_first_setup(idVendor=vid, idProduct=pid)
    else:
        gud = find_first_setup()

    if not gud:
        print('Failed to find a GUD device')
        return

    gud.controller_enable()

    print(f'Iterations: {args.iterations}\n')

    for state in states(gud, args.preferred_mode, fmt):
        print(state)
        gud.commit(state)
        # give time for modesetting to happen, at least the Pi is slow
        sleep(3)

        if gud.descriptor.compression & GUD_COMPRESSION_LZ4 and not args.no_compress:
            ratios = (None, 0, 1, 2, 3, 4, 8, 16)
        else:
            ratios = (None,)

        for ratio in ratios:
            if ratio is None:
                print(f'  No compress : ', flush=True, end='')
                tmin, tmean, tmax, parts = no_compression(gud, state, args.iterations)
            else:
                sr = f'x{ratio:d}'
                print(f'  Compress {sr:>3}: ', flush=True, end='')
                tmin, tmean, tmax, parts = compression_ratio(gud, state, ratio, args.iterations)
            split = f'(split:{parts})' if parts > 1 else ''
            print(f'{(1 / tmin):4.1f} > {(1 / tmean):4.1f} > {(1 / tmax):4.1f} fps ({(tmean * 1000):.3f} ms) {split}')
            # keep the last frame visible for a bit
            sleep(0.5)
        print()

    if not args.keep:
        gud.disable()
        gud.controller_disable()
        # This didn't work gives -EBUSY
        #gud.attach_kernel_driver()


def device_arg_check(arg):
    try:
        device_arg_split(arg)
    except Exception:
        raise argparse.ArgumentTypeError('Value has to be on the form: vid:pid')
    return arg


if __name__ == '__main__':
    modes = ' '.join([f'{mode[0]}x{mode[1]}' for mode in TEST_MODES])
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter,
        description=f'''
GUD performance tester

Runs tests directly to the device outside the kernel driver.

By default runs performance tests on:
- the first connected connector
- all formats (except ARGB8888 if XRGB8888 is supported)
- all modes covered by {modes} (if not use all modes)
''')
    parser.add_argument('--device', '-D', type=device_arg_check, help='Device to monitor: vid:pid (in hexadecimal)')
    parser.add_argument('-i', '--iterations', type=int, default=10, help='Number of flushes per test (default=10)')
    parser.add_argument('-k', '--keep', action='store_true', help="Don't disable display")
    parser.add_argument('-n', '--no-compress', action='store_true', help="Don't do the compression tests")
    parser.add_argument('-p', '--preferred-mode', action='store_true', help='Only use the preferred mode')
    parser.add_argument('-f', '--format', help='Only use the specified format (ARGB8888, XRGB8888, RGB565, XRGB1111, R1)')
    args = parser.parse_args()

    main(args)
