"""Tests for rteeg.stream.py"""
import numpy as np
from rteeg.stream import EEGStream, make_events, MarkerStream, _get_stream_inlet
from rteeg.tests.utils import SyntheticData, true_markers

def test_stream():
    # Create EEG and Marker streams / data.
    eeg_outlet = SyntheticData("EEG", 32, 100)
    eeg = EEGStream(eeg_system='Enobio32', lsl_predicate="type='EEG'")
    eeg.data = eeg_outlet.create_data(5000)

    marker_outlet = SyntheticData("Markers", 1, 1)
    markers = MarkerStream()
    markers.data = marker_outlet.create_data(10)

    # Test stream.make_events().
    test_markers = make_events(eeg.get_data(), markers)
    assert np.array_equal(true_markers, test_markers), "Markers not created properly."

    # Clean up.
    eeg_outlet.stop()
