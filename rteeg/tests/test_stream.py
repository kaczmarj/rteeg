"""Tests for rteeg.stream.py"""
from __future__ import division

import numpy as np
import pytest

from rteeg.stream import (_get_stream_inlet, SCALINGS EEGStream, make_events,
                          MarkerStream)
from rteeg.tests.utils import SyntheticData, true_markers

def test_scalings():
    assert SCALINGS['millivolts'] == SCALINGS['volts'] / 1e+3
    assert SCALINGS['microvolts'] == SCALINGS['volts'] / 1e+6
    assert SCALINGS['nanovolts'] == SCALINGS['volts'] / 1e+9

def test_get_stream_inlet():
    eeg_1 = SyntheticData("EEG", 32, 100, send_data=False)
    eeg_2 = SyntheticData("EEG", 32, 100, send_data=False)

    # Check for error if multiple matching streams exist.
    with pytest.raises(ValueError, message='Error on multiple streams'):
        _get_stream_inlet("type='EEG'")
    eeg_2.stop()  # Remove one LSL stream.

    # Check that inlet is of type pylsl.StreamInlet.
    inlet = _get_stream_inlet("type='EEG'")
    assert isinstance(inlet, StreamInlet), "Not pylsl.StreamInlet"
    eeg_1.stop()  # Clean up remaining LSL stream.

def test_make_events():
    eeg_out = SyntheticData("EEG", 32, 100)
    eeg = EEGStream(eeg_system='Enobio32', lsl_predicate="type='EEG'")
    eeg.data = eeg_out.create_data(5000)

    marker_outlet = SyntheticData("Markers", 1, 1)
    markers = MarkerStream()
    markers.data = marker_outlet.create_data(10)

    # Check that generated markers match the true markers.
    test_markers = make_events(eeg.get_data(), markers)
    assert np.array_equal(true_markers, test_markers), "Markers not created properly."

    # Check that empty events array is created if marker timestamps are out of
    # range of EEG timestamps.
    bad_timestamps_data = np.array(eeg.data)
    bad_timestamps_data[:, -1] *= -123.  # Change timestamps.
    bad_ts = np.array_equal(make_events(bad_timestamps_data, markers),
                            np.array([[0, 0, 0]]))
    assert bad_ts, "Empty events array not correct."

    # Clean up.
    eeg_out.stop()
