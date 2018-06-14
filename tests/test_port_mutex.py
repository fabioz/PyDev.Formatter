import pytest
import itertools


def test_port_mutex():
    from pydevf import PortMutex
    it = itertools.count(0)

    def on_create_server():
        return next(it)

    import weakref
    mutex_name = 'Port Mutex test'

    mutex = PortMutex(mutex_name, on_create_server)
    assert mutex.get_mutex_aquired()
    assert mutex.port == 0

    mutex2 = PortMutex(mutex_name, on_create_server)
    assert not mutex2.get_mutex_aquired()
    assert mutex2.port == 0
    del mutex2

    mutex.release_mutex()

    mutex3 = PortMutex(mutex_name, on_create_server)
    assert mutex3.get_mutex_aquired()
    assert mutex3.port == 1
    mutex3 = weakref.ref(mutex3)  # Garbage-collected

    # Calling release more times should not be an error
    mutex.release_mutex()

    mutex4 = PortMutex(mutex_name, on_create_server)
    assert mutex4.port == 2
    assert mutex4.get_mutex_aquired()

    with pytest.raises(AssertionError):
        PortMutex('mutex/', on_create_server)  # Invalid name
