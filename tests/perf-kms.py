#!/usr/bin/env python3

# SPDX-License-Identifier: CC0-1.0

import argparse
import mmap
import os
import statistics
from time import sleep
from timeit import default_timer as timer
import pykms

import lz4.block

def random(size, ratio):
    if ratio == 0:
        return bytes(os.urandom(size))

    zeroes = size - (size // ratio)
    buf = bytearray(zeroes) + bytearray(os.urandom(size - zeroes))

    want = len(buf) // ratio
    i = zeroes
    while i < size:
        compressed = lz4.block.compress(buf, return_bytearray=True, store_size=False)
        if len(compressed) <= want:
            break
        stride = (len(compressed) - want + 1) // 2
        if not stride:
            stride = 1
        buf[i : i + stride] = bytearray(stride) # Zeroes
        i += stride

    #print(f'actual ratio={(size/len(compressed))}')
    return bytes(buf)


TEST_MODES = ((1920, 1080), (1024, 768), (800, 600), (640, 480))

def test_modes(modes):
    if len(modes) <= len(TEST_MODES):
        return modes
    # trim down: use only TEST_MODES modes and filter out similar sizes
    tmodes = {}
    for mode in modes:
        size = (mode.hdisplay, mode.vdisplay)
        if size in TEST_MODES and not size in tmodes:
            tmodes[size] = mode
    if tmodes:
        return tmodes.values()
    return modes


def async_flush_disabled():
    async_path = '/sys/module/gud/parameters/async_flush'

    if not os.path.exists(async_path):
        print(f'File missing: {async_path} (added in Linux v5.15)')
        return False

    with open(async_path, 'r') as f:
        val = f.read()
    if val.strip() == 'N':
        return True

    try:
        with open(async_path, 'r+') as f:
            f.write('N')
    except PermissionError:
        print(f'Permission denied: {async_path} (run as root or write N to the file before running the script)')
        return False
    return True


def main(args):
    if not async_flush_disabled():
        return

    card = pykms.Card('gud', 0)
    res = pykms.ResourceManager(card)
    connector = res.reserve_connector()
    crtc = res.reserve_crtc(connector)
    plane = res.reserve_generic_plane(crtc)

    fb = None
    prev_fb = None

    if args.preferred_mode:
        modes = (connector.get_default_mode(),)
    else:
        modes = test_modes(connector.get_modes())

    if args.format:
        for fmt in plane.formats:
            if fmt.name == args.format:
                formats = [fmt]
                break
        else:
            print(f'Device does not support format: {args.format}')
            return
    else:
        formats = plane.formats

    # no point in testing two formats of the same size
    if {pykms.PixelFormat.ARGB8888, pykms.PixelFormat.XRGB8888} <= set(formats):
        formats.remove(pykms.PixelFormat.ARGB8888)

    ratios = (0, 1, 2, 3, 4, 8, 16)

    print(f'Iterations: {args.iterations}\n')

    for mode in modes:
        for fmt in formats:
            print(f'{mode.hdisplay}x{mode.vdisplay}@{fmt.name}')

            prev_fb = fb # keep fb from being destroyed and thus disabling the pipeline (enabling can be slow)

            fb = pykms.DumbFramebuffer(card, mode.hdisplay, mode.vdisplay, fmt);
            mm = mmap.mmap(fb.fd(0), fb.size(0))

            req = pykms.AtomicReq(card)
            req.add_connector(connector, crtc)
            modeb = mode.to_blob(card)
            req.add_crtc(crtc, modeb)
            req.add_plane(plane, fb, crtc)

            ret = req.commit_sync(allow_modeset = True)
            if ret < 0:
                raise OSError(-ret, os.strerror(-ret))

            # give time for modesetting to happen, at least the Pi is slow
            sleep(3)

            for ratio in ratios:

                sr = f'x{ratio:d}'
                print(f'  Compress {sr:>3}: ', flush=True, end='')

                buf = random(fb.size(0), ratio)
                mm.seek(0)
                mm.write(buf)

                elapsed = []
                for _ in range(args.iterations):
                    start = timer()
                    fb.flush()
                    end = timer()
                    elapsed.append(end - start)
                tmin = min(elapsed)
                tmean = statistics.mean(elapsed)
                tmax = max(elapsed)

                print(f'{(1 / tmin):4.1f} > {(1 / tmean):4.1f} > {(1 / tmax):4.1f} fps ({(tmean * 1000):.3f} ms)')

                # keep the frame visible for a bit
                sleep(0.5)
        print()


if __name__ == '__main__':
    modes = ' '.join([f'{mode[0]}x{mode[1]}' for mode in TEST_MODES])
    formats = ('XRGB8888', 'RGB565')

    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter,
        description=f'''
GUD performance tester

Tests various lz4 compression ratios.

By default runs performance tests on:
- the first detected gud device
- the first connected connector
- all formats (except ARGB8888 if XRGB8888 is supported)
- all modes covered by {modes} (if not use all modes)

Note:
  It cannot test R1 and XRGB1111 directly, but the driver converting
  from XRGB8888 is usually fast so it doesn't affect the result much.
''')
    parser.add_argument('-i', '--iterations', type=int, default=10, help='Number of flushes per test (default=10)')
    parser.add_argument('-p', '--preferred-mode', action='store_true', help='Only use the preferred mode')
    parser.add_argument('-f', '--format', choices=formats, help='Only use the specified format')
    args = parser.parse_args()

    main(args)
