"""Tests for rteeg.base.py"""
import threading
import time

import numpy as np
from pylsl import resolve_streams, StreamInlet
import pytest

from rteeg.base import BaseStream
from rteeg.tests.utils import SyntheticData


def test_BaseStream_record_data_indefinitely():
    # Start a LabStreamingLayer stream of synthetic data.
    eeg_out = SyntheticData("EEG", 32, 100, send_data=True)
    inlet = StreamInlet(resolve_streams()[0])
    base = BaseStream()
    # Check that length of base.data increases.
    len_0 = len(base.data)
    t = threading.Thread(target=base._record_data_indefinitely, args=(inlet,))
    t.start()
    time.sleep(5.)
    len_1 = len(base.data)
    assert len_1 > len_0, "Data not being recorded."
    # Clean up.
    eeg_out.stop()

def test_BaseStream_connect():
    def dummy_func():
        while True:
            time.sleep(5.)
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
