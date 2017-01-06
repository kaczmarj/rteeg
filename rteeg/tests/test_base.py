"""Tests for rteeg.base.py"""
import numpy as np
from rteeg.base import BaseStream
from rteeg.tests.utils import SyntheticData

def test_base():
    eeg_outlet = SyntheticData("EEG", 32, 100, send_data=False)
    base = BaseStream()
    base.data = eeg_outlet.create_data(5000)

    # Test BaseStream.copy_data()
    assert base.copy_data() is not base.data, "Copy of data not deep enough."
    copy_equal = np.array_equal(np.array(base.copy_data()), np.array(base.data))
    assert copy_equal, "The copy is not equivalent to the original."
    assert len(base.copy_data(index=100)) == 100, "Indexing failed."

    # Clean up.
    eeg_outlet.stop()
