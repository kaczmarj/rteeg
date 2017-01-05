"""Tests for rteeg.stream.py"""
from rteeg.stream import EEGStream, make_events, MarkerStream, _get_stream_inlet
from rteeg.tests.utils import SyntheticData, true_markers

eeg_outlet = SyntheticData("EEG", 32, 100)
eeg = rteeg.EEGStream(eeg_system='test', lsl_predicate="type='EEG'")
eeg.data = eeg_outlet.create_data(5000)

marker_outlet = SyntheticData("Markers", 1, 1)
markers = rteeg.MarkerStream()
markers.data = marker_outlet.create_data(10)

def test_stream():
    # Test stream.make_events().
    test_markers = rteeg.stream.make_events(eeg.get_data(), markers)
    assert np.array_equal(true_markers, test_markers), "Markers not created properly."
