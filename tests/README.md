GUD test suite
==============

A collection of tests that can be used to verify that a GUD device behaves as intended.
The tests disable the host driver and exercises the protocol directly through libusb.

Dependencies
------------

- python3
- numpy
- pytest
- pytest-repeat (optional)

Note: These need to be available for the root user since the tests need to be run as root.


Run protocol tests
------------------

```

# Run all protocol tests
$ sudo pytest tests/

# Run the request test and exit on first failure
$ sudo pytest tests/test_req.py -x

# Skip the stall tests that frequently locks up the Pi
$ sudo pytest tests/ -x -m 'not stall'

# Stress test (requires pytest-repeat)
$ sudo pytest tests/test_req.py --count 100 --repeat-scope session -x -m 'not stall'

```

Other tests
-----------

Get help with ```-h```

```
# Performance tests using various compression ratios
$ sudo python3 tests/perf.py

# Use default mode, RGB565 format, skip compressions and keep display enabled.
$ sudo python3 tests/perf.py -p -f RGB565 -n -k

# Test modes, formats, properties
$ sudo python3 tests/visual.py

# Test only the border test on the default display mode with format RGB565
$ sudo python3 tests/visual.py -p -f RGB565 border

```
