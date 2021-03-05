#!/usr/bin/env python

# Adapted from: https://jared.geek.nz/2013/feb/linear-led-pwm

from __future__ import print_function
import sys

if len(sys.argv) != 2:
    print("Usage: cie1931 OUTPUT_SIZE", file=sys.stderr)
    sys.exit(1)

INPUT_SIZE = 100                # Input integer size
OUTPUT_SIZE = int(sys.argv[1])  # Output integer size
TABLE_NAME = 'cie1931';

if OUTPUT_SIZE <= 2**8:
    INT_TYPE = 'static const uint8_t'
elif OUTPUT_SIZE <= 2**16:
    INT_TYPE = 'static const uint16_t'
elif OUTPUT_SIZE <= 2**32:
    INT_TYPE = 'static const uint32t'
else:
    print("OUTPUT_SIZE not supported")
    sys.exit(1)

def cie1931(L):
    L = L*100.0
    if L <= 8:
        return (L/903.3)
    else:
        return ((L+16.0)/119.0)**3

x = range(0,int(INPUT_SIZE+1))
y = [round(cie1931(float(L)/INPUT_SIZE)*OUTPUT_SIZE) for L in x]

# The GUD protocol states that brightness=0 should not turn off backlight completely,
# so change the first element which is zero
y[0] = y[1] / 2

print('%s %s[%d] = {' % (INT_TYPE, TABLE_NAME, INPUT_SIZE+1))
for i,L in enumerate(y):
    if i % 10 == 0:
        print('   ', end='')
    print(' %d,' % int(L), end='')
    if i % 10 == 9:
        print('')
print('\n};')
