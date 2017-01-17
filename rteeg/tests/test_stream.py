# Author: Jakub Kaczmarzyk <jakubk@mit.edu>
"""Tests for rteeg.stream.py"""
from __future__ import division

import threading
import time

from mne import Epochs
from mne.io import meas_info, RawArray
from mne.preprocessing.ica import ICA
import numpy as np
from pylsl import StreamInlet
import pytest

from rteeg import EEGStream, MarkerStream
from rteeg.stream import _get_stream_inlet, make_events, SCALINGS
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

def test_EEGStream():
    n_chs = 32
    sfreq = 100
    data_len = 5000
    eeg_out = SyntheticData("EEG", n_chs, sfreq, send_data=False)
    n_threads_1 = threading.active_count()
    eeg = EEGStream("Test", lsl_predicate="type='EEG'")
    time.sleep(5.)  # Allow some time for EEG stream to be found.
    n_threads_2 = threading.active_count()

    # Check that another thread was started.
    assert n_threads_2 - n_threads_1 == 1, "Thread not started."
    # Check for mne.Info object.
    assert isinstance(eeg.info, meas_info.Info), "Not mne.Info object."
    # Check for correct EEG unit.
    assert eeg._eeg_unit == "millivolts", "Wrong EEG unit."
    # Check for correct number of channels.
    assert len(eeg.info['ch_names']) == n_chs + 1, "Wrong number of channels."
    # Check for stim channel.
    assert "STI 014" in eeg.info['ch_names'], "Stim channel not present"
    # Check for sampling frequency.
    assert eeg.info['sfreq'] == sfreq, "Sampling frequency incorrect."
    # Check that ICA object is defined.
    assert isinstance(eeg.ica, ICA), "ICA object not defined."

    # Add data to eeg.data.
    eeg.data = eeg_out.create_data(data_len)

    # Check recording duration.
    assert eeg.get_recording_duration() == data_len / sfreq, "Duration incorrect."
    # Check that get_latency() does not raise error.
    assert eeg.get_latency(), "Latency incorrect."
    # Check resulting shape of get_data.
    assert eeg.get_data().shape == (n_chs + 1, data_len), "Shape of data copy incorrect."

    # Check that get_data() copies and scales the data properly.
    good_copy = np.array_equal(np.array(eeg.data)[:, :-1] * SCALINGS[eeg._eeg_unit],
                               eeg.get_data().T[:, :-1])
    assert good_copy, "Data not copied or scaled properly."
    # Check data_duration arg in get_data.
    assert eeg.get_data(1.).shape[1] == 1 * sfreq, "Duration arg not working."

    # Check EEGStream.make_raw()
    raw = eeg.make_raw()
    # Check the type of raw object.
    assert isinstance(raw, RawArray), "Incorrect type."
    # Check number of channels.
    assert len(raw.ch_names) == n_chs + 1, "Number of channels incorrect."
    # Check number of samples.
    assert raw.n_times == data_len, "Number of samples incorrect."
    # Check sampling frequency in raw object.
    assert raw.info['sfreq'] == sfreq, "Incorrect sampling frequency."

    # TODO: test whether ICA works.
    # TODO: test that data is being added.


    # Check EEGStream.make_epochs()
    marker_out = SyntheticData("Markers", 1, 1, send_data=False)
    markers = MarkerStream()
    time.sleep(5.)  # Allow some time for Marker stream to be found.
    markers.data = marker_out.create_data(10)
    epochs = eeg.make_epochs(markers)
    # Check the type of epochs object.
    assert isinstance(epochs, Epochs), "Incorrect type."
    # Check number of channels.
    assert len(epochs.ch_names) == n_chs + 1, "Number of channels incorrect."
    # Check number of events.
    assert np.array_equal(epochs.events, true_markers), "Events incorrect."

    # TODO: test EEGStream.fit_ica() and EEGStream.viz_ica()

    # Clean up.
    eeg_out.stop()
    marker_out.stop()

def test_MarkerStream():
    marker_out = SyntheticData("Markers", 1, 1, send_data=False)
    n_threads_1 = threading.active_count()
    markers = MarkerStream()
    n_threads_2 = threading.active_count()

    # Check that thread was started.
    assert n_threads_2 - n_threads_1 == 1, "Thread not started."

    # TODO: test that data is being added.

    # Clean up.
    marker_out.stop()
