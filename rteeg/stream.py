# Author: Jakub Kaczmarzyk <jakubk@mit.edu>
from __future__ import division

import datetime
import numbers
import time
import warnings

from mne import concatenate_raws, create_info, Epochs, io, set_log_level
from mne.preprocessing import ICA
from mne.utils import ProgressBar
import numpy as np
from pylsl import StreamInlet, local_clock, resolve_bypred

from .base import BaseStream
import default_predicates

# How much MNE talks.
set_log_level(verbose='error')

# Always print warnings.
warnings.filterwarnings(action='always', module='rteeg')

# MNE wants EEG values in volts.
SCALINGS = {
    'volts': 1.,
    'millivolts': 1. / 1e+3,
    'microvolts': 1. / 1e+6,
    'nanovolts': 1. / 1e+9,
    'unknown': 1.,
}


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



class EEGStream(BaseStream):
    """
    Parameters
    ----------
    eeg_system : {'Enobio32'}
        The EEG system being used. This name indicates which predicate to use
        in `default_predicates.py`.
    lsl_predicate : str
    """
    def __init__(self, eeg_system, lsl_predicate=None):
        super(EEGStream, self).__init__()
        self.eeg_system = eeg_system
        self.lsl_predicate = lsl_predicate
        if self.lsl_predicate is None:
            try:
                self.lsl_predicate = default_predicates.eeg[eeg_system]
            except KeyError:
                raise ValueError("The `eeg_system` {} has no LabStreamingLayer "
                                 "predicate defined in `default_predicates`. "
                                 "Without a valid predicate, streams cannot be "
                                 "found.".format(self.eeg_system))
        self.ica = ICA(method='extended-infomax')
        self.raw_for_ica = None
        # Search for and connect to a LabStreamingLayer stream of EEG data.
        self.connect(self._connect, 'EEG-data')

    def _connect(self):
        """Connect to stream and record data to list."""
        self._stream_inlet = _get_stream_inlet(self.lsl_predicate)

        # Extract stream info.
        info = self._stream_inlet.info()

        # Get sampling frequency.
        sfreq = float(info.nominal_srate())

        # Get channel names.
        ch_names = []
        this_child = info.desc().child('channel')
        for __ in range(info.channel_count()):
            ch_names.append(this_child.child_value('name'))
            this_child = this_child.next_sibling('channel')

        # Get the EEG measurement unit (e.g., microvolts).
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

        # Add stimulus channel.
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
        self._record_data_indefinitely(self._stream_inlet)

    def get_latency(self):
        """Return the recording latency (current time minus last timestamp).

        There is a weird bug in this method. Last timestamp looks like it does
        not change. For example, if you call this method, wait 3 seconds, and
        call it again, it will say the latency is 3 seconds. Is it related to
        locking? Refreshing something about the last item in `data`? But the
        lock releases after returning. Not sure how to replicate this bug. Lock
        is not necessary here.
        """
        return local_clock() - self.data[-1][-1]

    def get_recording_duration(self):
        """Return duration of recording in seconds (equals n_samples / sfreq).
        """
        return len(self.data) / self.info['sfreq']

    def get_data(self, data_duration=None, scale=None):
        """Return EEG data and timestamps.

        Parameters
        ----------
        data_duration : int
            Window of data to output in seconds. If None, will return all of
            the EEG data.
        scale : int, float
            Value by which to multiply the EEG data. If None, attempts to
            scale values to volts.

        Returns
        -------
        data : ndarray
            Array of EEG data with shape (n_channels + timestamp, n_samples).
        """
        if scale is None:
            scale = SCALINGS[self._eeg_unit]
        if data_duration is None:
            data = np.array(self.copy_data()).T
            # Scale the data but not the timestamps.
            data[:-1,:] = np.multiply(data[:-1,:], scale)
        else:
            index = int(data_duration * self.info['sfreq'])
            data = np.array(self.copy_data(index)).T
            # Scale the data but not the timestamps.
            data[:-1,:] = np.multiply(data[:-1,:], scale)
        return data

    def make_raw(self, data_duration=None, apply_ica=True, first_samp=0,
                 verbose=None, marker_stream=None):
        """Create instance of mne.io.RawArray.

        Parameters
        ----------
        data_duration : int, float
            Duration of previous data to use. If data=10, returns instance of
            mne.io.RawArray of the previous 10 seconds of data.
        apply_ica : bool (defaults to True)
            If True and self.ica has been fitted, will apply the ICA to the
            requested data. If False, will not fit ICA to the data.
        first_samp : int (defaults to 0)
            Sample offset.

        Returns
        -------
        raw : mne.io.RawArray
            The EEG data.
        """
        raw_data = self.get_data(data_duration=data_duration)
        # Add events if Markers stream was started.
        if marker_stream is None:
            raw_data[-1,:] = 0  # Make row of timestamps a row of events 0.
            raw = io.RawArray(raw_data, self.info, first_samp=first_samp,
                              verbose=verbose)
        else:
            raw = io.RawArray(raw_data, self.info, first_samp=first_samp,
                              verbose=verbose)
            events = self.make_events(raw_data, marker_stream)
            raw_data[-1,:] = 0  # Replace timestamps with zeros.
            raw.add_events(events)
        # If user wants to apply ICA and if ICA has been fitted ...
        if apply_ica and self.ica.current_fit != 'unfitted':
            return self.ica.apply(raw)
        return raw

    def make_events(self, data, marker_stream, event_duration=0):
        """Create array of events.

        This function creates an array of events that is compatible with
        mne.Epochs. If no marker is found, returns ndarray indicating that
        one event occurred at the same time as the first sample of the EEG data,
        effectively making an Epochs object out of all of the data (until tmax
        of mne.Epochs)

        Parameters
        ----------
        data : array
            EEG data in the shape (n_channels + timestamp, n_samples). Call
            the method _get_raw_eeg_data() to create this array.
        marker_stream : rteeg.MarkerStream
            Stream of marker data.
        event_duration : int (defaults to 0)
            Duration of each event marker in seconds. This is not epoch
            duration.

        Returns
        -------
        events : ndarray
            Array of events in the shape (n_events, 3).
        """
        # Get the markers between two times.
        lower_time_limit = data[-1,0]
        upper_time_limit = data[-1,-1]
        with marker_stream._thread_lock:
            tmp = np.array([row[:] for row in marker_stream.data
                             if upper_time_limit >= row[-1] >= lower_time_limit],
                             dtype=np.int32)
        # Pre-allocate array for speed.
        events = np.zeros(shape=(tmp.shape[0], 3), dtype=np.int32)
        # If there is at least one marker ...
        if tmp.shape[0] > 0:
            for event_index, (marker_int, timestamp) in enumerate(tmp):
                # Get the index where this marker happened in the EEG data.
                eeg_index = (np.abs(data[-1,:] - timestamp)).argmin()
                # Add a row to the events array.
                events[event_index, :] = eeg_index, event_duration, marker_int
        else:
            # Make empty events array.
            return np.array([[0, 0, 0]])
        return events

    def make_epochs(self, marker_stream, data_duration=None, events=None,
                    event_duration=0, event_id=None, apply_ica=True, tmin=-0.2,
                    tmax=1.0, baseline=(None, 0), picks=None, name='Unknown',
                    preload=False, reject=None, flat=None, proj=True, decim=1,
                    reject_tmin=None, reject_tmax=None, detrend=None,
                    add_eeg_ref=None, on_missing='error', reject_by_annotation=True,
                    verbose=None):
        """Create instance of mne.Epochs. If events are not supplied, this
        script must be connected to a Markers stream.

        Parameters
        ----------
        marker_stream : rteeg.MarkerStream
            Stream of marker data.
        data_duration : int, float
            Duration of previous data to use. If data=10, returns instance of
            mne.Epochs of the previous 10 seconds of data.
        events : ndarray
            Array of events of the shape (n_events, 3)
        Copy parameters from mne.Epochs

        apply_ica : bool (defaults to True)
            If True and if self.ica has been fitted, will apply the ICA to the
            requested data. If False, will not fit ICA to the data.

        Returns
        -------
        epochs : mne.Epochs
        """
        raw_data = self.get_data(data_duration=data_duration)

        if events is None:
            events = self.make_events(raw_data, marker_stream, event_duration)

        raw_data[-1,:] = 0
        raw = io.RawArray(raw_data, self.info)

        # If user wants to apply ICA and if ICA has been fitted ...
        if apply_ica and self.ica.current_fit != 'unfitted':
            raw = self.ica.apply(raw)

        return Epochs(raw, events, event_id=event_id, tmin=tmin, tmax=tmax,
                      baseline=baseline, picks=picks,name=name, preload=preload,
                      reject=reject, flat=flat, proj=proj, decim=decim,
                      reject_tmin=reject_tmin, reject_tmax=reject_tmax,
                      detrend=detrend, add_eeg_ref=add_eeg_ref,
                      on_missing=on_missing,
                      reject_by_annotation=reject_by_annotation, verbose=verbose)

    def fit_ica(self, data, when='next', warm_start=False):
        """Conduct Independent Components Analysis (ICA) on a segment of data.

        The fitted ICA object is stored in the variable ica. Noisy components
        can be selected in the ICA, and then the ICA can be applied to incoming
        data to remove noise. Once fitted, ICA is applied by default to data
        when using the methods make_raw() or make_epochs().

        Components marked for removal can be accessed with self.ica.exclude.

        Use example:

        >>> rt = Stream()
        >>> rt.connect(eeg=True)  # Connect to LSL stream of EEG data.
        >>> rt.fit_ica(10)  # Fit the ICA on the next 10 seconds of data.
        >>> # Plot the ICA sources and click on components to mark for removal
        >>> rt.ica.plot_sources(rt.raw_for_ica)
        >>> # Assuming at least one component was marked for removal, visualize
        >>> # the effects of removing the component(s) in raw data.
        >>> rt.ica.apply(rt.raw_for_ica).plot()


        data : int, float, mne.RawArray
            The duration of previous or incoming data to use to fit the ICA, or
            an mne.RawArray object of data.
        when : {'previous', 'next'} (defaults to 'next')
            Whether to compute ICA on the previous or next X seconds of data.
            Can be 'next' or 'previous'. If data is type mne.RawArray, this
            parameter is ignored.
        warm_start : bool (defaults to False)
            If True, will include the EEG data from the previous fit. If False,
            will only use the data specified in the parameter data.
        """
        # Re-define ICA variable to start ICA from scratch if the ICA was
        # already fitted and user wants to fit again.
        if self.ica.current_fit != 'unfitted':
            self.ica = ICA(method='extended-infomax')

        if type(data) is io.RawArray:
            self.raw_for_ica = data

        elif isinstance(data, numbers.Number):
            user_index = int(data * self.info['sfreq'])
            if when.lower() not in ['previous', 'next']:
                raise ValueError("when must be 'previous' or 'next'. {} was "
                                 "passed.".format(when))
            elif when == 'previous':
                end_index = len(self.data)
                start_index = end_index - user_index
                # TODO: Check if out of bounds.

            elif when == 'next':
                start_index = len(self.data)
                end_index = start_index + user_index
                # Wait until the data is available.
                pbar = ProgressBar(end_index - start_index,
                                   mesg="Collecting data")
                while len(self.data) <= end_index:
                    # Sometimes sys.stdout.flush() raises ValueError. Is it
                    # because the while loop iterates too quickly for I/O?
                    try:
                        pbar.update(len(self.data) - start_index)
                    except ValueError:
                        pass
                print("")

            with self._thread_lock:
                 _data = np.array([r[:] for r in
                                   self.data[start_index:end_index]]).T

            # Now we have the data array in _data. Use it to make instance of
            # mne.RawArray, and then we can compute the ICA on that instance.
            _data[-1,:] = 0

            # Use previous data in addition to the specified data when fitting
            # the ICA, if the user requested this.
            if warm_start and self.raw_for_ica is not None:
                self.raw_for_ica = concatenate_raws(
                    [self.raw_for_ica, io.RawArray(_data, self.info)])
            else:
                self.raw_for_ica = io.RawArray(_data, self.info)

        print("Computing ICA solution ...")
        t0 = local_clock()
        self.ica.fit(self.raw_for_ica.copy())  # Fits in-place.
        print("Finished in {:.2f} s".format(local_clock() - t0))


    def viz_ica(self, plot='components'):
        """Visualize data with components removed.

        User decides whether to plot ICA components or EEG data with selected
        components removed.

        If user wants to change which components should be removed, simply call
        this function again, and change the selection on the plot of latent ICA
        components.

        plot : {'components', 'scalp_components', 'cleaned_data'}
            'components' : Plot the latent ICA components. Components to be
                           removed are selected on this plot.
            'map_components' : Plot the distribution of components across
                               the scalp.
            'cleaned_data' : Plot sample of EEG data with specified components
                             zeroed out. Warns if no components were selected
                             for removal.

        Notes
        -----
        It would be better to show the components plot and the cleaned data plot
        after the user closes the components plot. This would require the first
        plot to block, but blocking these plots is not supported by all systems.
        """
        if self.ica.current_fit == 'unfitted' or self.raw_for_ica is None:
            raise RuntimeError("ICA has not been fit yet or data used to "
                               "fit ICA does not exist. Fit ICA before "
                               "calling this function again.")

        if plot == 'components':
            return self.ica.plot_sources(self.raw_for_ica)
        elif plot == 'map_components':
            return self.ica.plot_components()
        elif plot == 'cleaned_data':
            if not self.ica.exclude:
                warnings.warn("No ICA components were marked for removal. EEG "
                              "data has not been changed.")
            print("Components to be removed: {}".format(self.ica.exclude))
            return self.ica.apply(self.raw_for_ica.copy()).plot()



class MarkerStream(BaseStream):
    """Docstring here"""
    def __init__(self, lsl_predicate_key='default'):
        super(MarkerStream, self).__init__()
        self.lsl_predicate_key = lsl_predicate_key
        self.lsl_predicate = default_predicates.markers[self.lsl_predicate_key]
        self.connect(self._connect, 'Marker-data')

    def _connect(self):
        """Connect to stream and record data to list."""
        self._stream_inlet = _get_stream_inlet(self.lsl_predicate)
        self._record_data_indefinitely(self._stream_inlet)
