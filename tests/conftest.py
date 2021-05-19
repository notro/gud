import pytest
from gud import *

@pytest.fixture(name='dev', scope='session')
def gud_device():
    dev = find()
    if not dev:
        raise "No device"
    if dev.is_kernel_driver_active(0):
        dev.detach_kernel_driver(0)
    dev.reset()
    dev.config()
    return dev


@pytest.fixture(name='gud', scope='session')
def gud_device_ready(dev):
    for connector in dev.connectors:
        connector.update()
    return dev


@pytest.fixture()
def state(gud): #, update_connectors):
    s = State(gud)
    s.check()
    s.commit()
    return s
