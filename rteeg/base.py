"""Author: Jakub Kaczmarzyk, jakubk@mit.edu

Should we make a thread-safe list class?


Free functions:
x    resolve_streams()
    _check_data_index()
    _get_stream_inlet()

BaseStream:
    Attributes:
        _stream_inlet
        _thread
        _thread_lock
        _kill_signal

    Methods:
        __init__
        __del__
        _connect() (in thread)
        connect()  (call at end of __init__)
        _grab_data_indefinitely()

        New methods:
            get_last_timestamp()

Methods not included in base:
    available_streams()
    _check_if_stream_active()
    disconnect()
    reconnect()
    recording_duration()
    eeg_latency()
    _get_raw_eeg_data()
    make_events()
    make_raw()
    make_epochs()
    fit_ica()
    viz_ica()

Attributes not included in base:
    active_streams
"""
from __future__ import division
import datetime
from threading import Event, RLock, Thread
import time
import warnings

from mne import create_info
import numpy as np
from pylsl import (StreamInlet, local_clock, resolve_bypred, resolve_byprop,
                   resolve_streams)

warnings.filterwarnings(action='always', module='rteeg')


def resolve_streams():
    """Return list of available LabStreamingLayer streams."""
    return resolve_streams()

def _check_data_index():
    pass

def _get_stream_inlet(lsl_predicate):
    """Return the stream that fits the given predicate. Raise ValueError if
    multiple streams or zero streams match the predicate.

    Parameters
    ----------
    lsl_predicate : str
        Predicate used to find LabStreamingLayer stream. See
        `default_eeg_predicates.py` for more info.

    Returns
    -------
    inlet : pylsl.StreamInlet
        The LSL stream that matches the given predicate.
    """
    stream = resolve_bypred(lsl_predicate)
    if len(stream) == 1:
        inlet = StreamInlet(stream[0])
        print("Connected to stream.")
    elif not stream:
        raise ValueError("Zero streams match the given predicate.")
    else:
        raise ValueError("Multiple streams match the given predicate. Only one "
                         "stream must match the predicate.")
    return inlet



class BaseStream(object):

    def __init__(self, stream_type, lsl_predicate, eeg_system=None):
        self.stream_type = stream_type
        self.lsl_predicate = lsl_predicate
        self.eeg_system = eeg_system

        self._thread = None
        self._thread_lock = RLock()
        self._kill_signal = Event()

        self.data = []
        # self._stream_inlet = None

        # self._thread = None

    def __del__(self):
        self._kill_signal.set()

    def _record_data_indefinitely(self):
        """Record data to list, and correct for time differences between
        machines.
        """
        while not self._kill_signal.is_set():
            sample, timestamp = self._stream_inlet.pull_sample()
            time_correction = self._stream_inlet.time_correction()
            sample.append(timestamp + time_correction)
            with self._thread_lock:
                self.data.append(sample)

    def _connect(self):
        """Connect to stream and record data to list."""
        self._stream_inlet = _get_stream_inlet(self.lsl_predicate)

        # Get EEG metadata if connecting to an EEG stream.
        if self.stream_type == 'EEG':
            # Extract stream info.
            info = inlet.info()

            # Get sampling frequency.
            sfreq = float(info.nominal_srate())

            # Get channel names.
            ch_names = []
            this_child = info.desc().child('channel')
            for __ in range(info.channel_count()):
                ch_names.append(this_child.child_value('name'))
                this_child = this_child.next_sibling('channel')

            # Get the EEG measurement unit (e.g., microvolts)
            units = []
            this_child = info.desc().child('channel')
            for __ in range(info.channel_count()):
                units.append(this_child.child_value('unit'))
                this_child = this_child.next_sibling('channel')
            if all(units):
                self._eeg_unit = units[0]
            else:
                warnings.warn("Could not find EEG measurement unit.")
                self._eeg_unit = 'unknown'

            # Add stim channel.
            ch_types = ['eeg' for __ in ch_names] + ['stim']
            ch_names.append('STI 014')

            # Create mne.Info object.
            self.info = create_info(ch_names=ch_names,
                                    sfreq=sfreq, ch_types=ch_types,
                                    montage=self.eeg_system)

            # Add time of recording.
            d = datetime.datetime.now()
            timestamp = time.mktime(d.timetuple())
            self.info['meas_date'] = [timestamp, 0]

        # Record data in a while loop.
        self._record_data_indefinitely()




















#
