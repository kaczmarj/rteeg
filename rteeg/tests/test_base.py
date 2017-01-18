# Author: Jakub Kaczmarzyk <jakubk@mit.edu>
"""Tests for rteeg.base.py"""
from __future__ import division, print_function
import random
import threading
import time

import numpy as np
from pylsl import resolve_streams, StreamInlet
import pytest

from rteeg.base import BaseStream, ThreadSafeList
from rteeg.tests.utils import SyntheticData, check_equal

# Clean up BaseStream tests. Make it one function to be consistent with other
# tests.

def test_BaseStream_record_data_indefinitely():
    """Test rteeg.base.BaseStream"""
    # Start a LabStreamingLayer stream of synthetic data.
    eeg_out = SyntheticData("EEG", 32, 100, send_data=True)
    inlet = StreamInlet(resolve_streams(wait_time=1.)[0])
    base = BaseStream()

    # Check that length of base.data increases.
    len_0 = len(base.data)
    t = threading.Thread(target=base._record_data_indefinitely, args=(inlet,))
    t.daemon = True
    t.start()
    time.sleep(2.)
    len_1 = len(base.data)
    assert len_1 > len_0, "Data not being recorded."

    # Clean up.
    base._kill_signal.set()
    eeg_out.stop()

def test_BaseStream_connect():
    event = threading.Event()
    def dummy_func():
        while not event.is_set():
            time.sleep(1.)
    base = BaseStream()
    n_threads_0 = threading.active_count()
    base.connect(dummy_func, "TEST")
    n_threads_1 = threading.active_count()
    # Check that a thread was started.
    assert n_threads_1 - n_threads_0 == 1, "Thread not started."

    # Check that the thread was created and named properly.
    name = [t.getName() for t in threading.enumerate() if t.getName() == "TEST"]
    assert name[0] == "TEST", "Thread not named properly."

    # Check that connect method only allows one connection.
    with pytest.raises(RuntimeError):
        base.connect(dummy_func, "SECOND_TEST")

    # Clean up.
    event.set()

def test_BaseStream_copy_data():
    # Start a LabStreamingLayer stream but do not stream data.
    eeg_outlet = SyntheticData("EEG", 32, 100, send_data=False)
    base = BaseStream()

    # Create the data.
    base.data = eeg_outlet.create_data(5000)
    assert base.copy_data() is not base.data, "Copy of data not deep enough."
    copy_equal = np.array_equal(np.array(base.copy_data()), np.array(base.data))
    assert copy_equal, "The copy is not equivalent to the original."
    assert len(base.copy_data(index=100)) == 100, "Indexing failed."

    # Clean up.
    eeg_outlet.stop()


def test_ThreadSafeList():
    """Test rteeg.base.ThreadSafeList"""
    # Test list-like functionality.
    # Add list addition, subtraction, multiplication, division, sorting, etc.

    iterable = [[i * 2] * 3 for i in range(5)]
    data = ThreadSafeList(iterable)
    assert data._list == iterable, "List not created properly."
    assert len(data) == 5, "__len__ method broken."
    assert [len(row) for row in data] == [3] * 5, "len of nested lists incorrect."
    assert data[1] == [2] * 3, "__getitem__ method broken."
    assert [row[:] for row in data] == iterable, "List comprehension broken."
    del data[0]
    assert len(data) == 4, "__del__ method broken."
    data.insert(0, 999)
    assert data[0] == 999, "insert method broken."
    data.append([10, 11, 12])
    assert data[-1] == [10, 11, 12], "append method broken."
    data.extend([100, 101, 102])
    assert data[-3:] == [100, 101, 102], "extend method broken."
    data[-1] = 1234
    assert data[-1] == 1234, "__setitem__ method broken"
    # Clean up.
    data = None
    iterable = None


    # Test thread-safety by running a stress test:
    #   1. Add lists quickly to a base Python list with and without a lock and
    #      to a ThreadSafeList instance.
    #   2. Copy the base Python list with and without the lock, and copy the
    #      ThreadSafeList instance without a lock.
    #   3. For each type of list, check whether the len of all nested lists are
    #      equal. The base Python list without the lock is expected to have
    #      unequal lens, but the other lists should have equal lens.
    N_ROWS = 20
    SLEEP_TIME = 0.002  # equivalent to 500 Hz
    # Each function will continually add one of these lists as a "column".
    column1 = [random.random() for _ in range(N_ROWS)]
    column2 = [random.random() for _ in range(N_ROWS)]

    kill_signal = threading.Event()
    rlock = threading.RLock()

    regular = [[]] * N_ROWS
    def locked_synth():
        """Add to Python list 'column-wise' (similar to numpy.hstack()) under a
        threading.RLock object."""
        while not kill_signal.is_set():
            with rlock:
                for x, y in zip(regular, column1):
                    x.append(y)
                time.sleep(SLEEP_TIME)

    thread_safe = ThreadSafeList([[]] * N_ROWS)
    def unlocked_synth():
        """Add to thread-safe list class 'column-wise' (similar to
        numpy.hstack()) without a lock object."""
        while not kill_signal.is_set():
            for x, y in zip(thread_safe, column2):
                x.append(y)
            time.sleep(SLEEP_TIME)

    # Regular list.
    t1 = threading.Thread(target=locked_synth)
    t1.start()
    # Custom class.
    t2 = threading.Thread(target=unlocked_synth)
    t2.start()

    time.sleep(5.0)  # Give the threads time to add data.

    # Get len of nested lists within each list.
    regular_unlock_copy = [[item for item in row] for row in regular]
    thread_copy = [[item for item in row] for row in thread_safe]
    with rlock:
        regular_lock_copy = [[item for item in row] for row in regular]

    # Check that lens are equal in all cases except in unlocked case.
    assert check_equal([len(row) for row in thread_copy]), "ThreadSafeList not thread-safe."
    assert not check_equal([len(row) for row in regular_unlock_copy]), "Test broken."
    assert check_equal([len(row) for row in regular_lock_copy]), "Test broken."

    # Clean up.
    kill_signal.set()
    t1.join()
    t2.join()
