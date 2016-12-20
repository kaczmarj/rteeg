"""Stream and analyze EEG data in real-time.


KEEP IN MIND
------------
- ICA before filtering (according to Satra).
- read (http://stackoverflow.com/questions/29402606/
    possible-to-create-a-synchronized-decorator-thats-aware-of-a-methods-object)

TO DO
-----
- Implement scaling for EEG. Divide raw data by 1000000. How can we define a
    default scaling factor for each system?
- Check whether LSL stream broke off.
    If stream breaks off, warning is written in the terminal running Jupyter
    Notebook. Stream reconnects automatically, assuming the same unique ID was
    used as when it was started.
- Offset between last LSL sample and current time?
- Synchronization of timestamps between streams?
- Check for existence of EEG and Markers streams.
- Record with Coregui and with this real-time script. See if identical.
- Check if this works with BioSemi cap.
- Try classifying something easy (hearing a sound versus no sound).
- Implement verbose support.
- Change docstring style?
- Get rid of disconnect and reconnect methods?


ISSUES
------
- Bug in events. For some reason, sometimes the event duration gets the event
    ID. Why?
- If recording for a while, there is a pretty large offset between markers in
    Coregui and markers in this script. Why? Should we get the EEG data by
    pull_chunk instead of pull_sample? Would that even help?
    #### It's probably the latency between the EEG hardware and Coregui...
         There was a delay of 202564 ms... 3 minutes! That is roughly equal to
         the delay between Coregui and the script.
- How to run the loop of data processing / classification?
    - Everytime buffer fills up, trigger. (python `select` module?)
    - How to query size of buffer? Open up another stream which constantly gets
    the current buffer size, and trigger something using that.
    - Or use if-else to trigger only if the buffer is at least some size?
- How to create classifier during experiment? Update classifier?
- Known issue with pylsl 1.10.5: On Linux one currently cannot call pylsl
functions from a thread that is not the main thread. rteeg would not work.
- How does one build pylsl on a Mac or on Linux?


LOOK INTO
---------
- Poll and trigger
- ImageNet (and related paper by DiCarlo's group, 2014).
- Nextflow (data flow)
- Maybe make different classes to support different EEG devices. Or include the
default LSL predicates in a dictionary, where each key is an EEG device.
- What if user wants to input their own mne.Info object??


NOTES
-----
- If the EEG or Markers stream was somehow disconnected (e.g., Coregui crashed),
rteeg will reconnect to the stream once it comes back (as long as it has the
same unique ID as before it was lost).


Author: Jakub Kaczmarzyk, jakubk@mit.edu
"""
from __future__ import division

import datetime
import numbers
from threading import Event, RLock, Thread
import time
import warnings
from xml.etree import ElementTree as ET

from mne import concatenate_raws, create_info, Epochs, io, set_log_level
from mne.preprocessing import ICA
from mne.utils import ProgressBar

import numpy as np

from pylsl import (StreamInlet, local_clock, resolve_bypred, resolve_byprop,
                   resolve_streams)


# Set MNE verbosity.
# In the future, include this verbosity in a global verbosity setting.
set_log_level(verbose='error')

# Always print warnings.
warnings.filterwarnings(action='always', module='rteeg')


def _get_stream_inlet(type_='EEG', lsl_predicate=None):
    """Return the stream that fits the given predicate. Raise ValueError if
    multiple streams or zero streams match the predicate.

    Parameters
    ----------
    type : {'EEG', 'Markers'}
        The type of LSL stream. Defaults to 'EEG' (case-insensitive).
    lsl_predicate : str (copied from pylsl.resolve_bypred())
        The predicate string, e.g. "name='BioSemi'" or
        "type='EEG' and starts-with(name,'BioSemi') and
        count(description/desc/channels/channel)=32". For more info, refer to:
        http://en.wikipedia.org/w/index.php?title=XPath_1.0&oldid=474981951.

    Returns
    -------
    inlet : pylsl.StreamInlet
        The LSL stream that matches the given predicate.
    """
    if type_.lower() not in ['eeg', 'markers']:
        raise ValueError("`type` must be 'EEG' or 'Markers'. "
                         "'{}' was passed".format(type_))

    print("Searching for {} stream ... ".format(type_))

    default_predicates = {
        'eeg': "type='EEG' and starts-with(desc/manufacturer,'NeuroElectrics')",
        'markers': "type='Markers' and "
                   "not(starts-with(desc/manufacturer,'NeuroElectrics'))",
    }

    if lsl_predicate is None:
        lsl_predicate = default_predicates[type_.lower()]

    stream = resolve_bypred(lsl_predicate)

    if len(stream) == 1:
        inlet = StreamInlet(stream[0])
        print("Connected to {} stream. ".format(type_))
    elif not stream:
        raise ValueError("No streams of type '{}' are available.".format(type_))
    else:
        raise ValueError("Multiple streams of type '{}' are available. Script "
                         "requires that there only be one stream of type '{}' "
                         "with the given predicate".format(type_))

    return inlet


def _grab_data_indefinitely(lsl_inlet, list_, rlock, kill_signal):
    """Append data and timestamp to nested list until a kill signal is received.
    Modifies list_ in-place. If this function is called within a separate
    thread, the constantly-growing list_ can be accessed from the main thread.

    Parameters
    ----------
    lsl_inlet : pylsl.StreamInlet
        The StreamInlet of EEG or Markers data.
    list_ : list
        The list to which data is appended.
    rlock : threading.RLock
        Reentrant lock to make appending and accessing data thread-safe.
    kill_signal : threading.Event
        If set, while loop will exit.
    """
    # Get time offset and add it to the timestamps to synchronize streams.
    time_correction = lsl_inlet.time_correction()

    while not kill_signal.is_set():
        sample, timestamp = lsl_inlet.pull_sample()
        sample.append(timestamp + time_correction)
        with rlock:
            list_.append(sample)

    return None


def _check_data_index(desired_index, data):
    """Check whether user is requesting more data than exists. Warn if
    desired_index is out of bounds of data.

    Parameters
    ----------
    desired_index : int
        The index of the data the user wants to access.
    data : ndarray
        The data the user wants to access.
    """
    current_max = len(data)
    if desired_index > current_max:
        warnings.warn("Last {} samples were requested, but only {} are "
                      "present.".format(desired_index, current_max))

    return True



class Stream(object):
    """Class to connect to a LabStreamingLayer stream of EEG and/or Markers
    data and to copy the data for analysis in MNE-Python.

    Attributes
    ----------
    active_streams : dict of str: bool
        Indicates whether EEG and/or Markers stream is active.
    _stream_inlet_objects : dict
        Dictionary of stream type and the corresponding pylsl.StreamInlet.
    _threads : dict
        Dictionary of stream type and the corresponding threading.Thread.
    _thread_locks : dict
        Dictionary of stream type and the corresponding threading.RLock.
    _kill_signals : dict
        Dictionary of stream type and the corresponding kill signal
        (threading.Event).
    _disconnected_streams : dict
        Dictionary of stream type and whether that stream was disconnected.
    _eeg_data : list
        Growing nested list of EEG data.
    _marker_data : list
        Growing nested list of Markers data.
    info : mne.Info
        Metadata associated with the EEG data.
    ica : mne.preprocessing.ICA
        ICA object used to remove artifacts from the EEG data. Uses
        'extended-infomax' method by default.
    raw_for_ica : mne.RawArray
        The raw data on which the ICA solution is computed.



    Use example:

    In [1]: %matplotlib qt

    In [2]: import rteeg

    In [3]: rt = rteeg.Stream()

    In [4]: rt.connect(eeg=True, markers=True, eeg_montage='Enobio32')
    Searching for EEG stream ...
    Searching for Markers stream ...

    In [5]:
    Connected to Markers stream. Connected to EEG stream.

    In [5]: print rt.recording_duration()
    80.15

    In [6]: rt.fit_ica(10)  # Fit ICA on next 10 seconds of data.
    [........................................] 100.00000 | Collecting data
    Computing ICA solution ...
    Finished in 0.82 s
    Out[6]: <ICA  |  raw data decomposition, fit (extended-infomax): 1000
    samples, 32 components, channels used: "eeg">

    In [7]: rt.ica.plot_sources(rt.raw_for_ica)
    Out[7]: <matplotlib.figure.Figure at 0x11c1a5150>

    In [8]: print(rt.ica.exclude)  # Components marked for exclusion.
    [1, 2]

    In [9]: rt.ica.apply(rt.raw_for_ica).plot(scalings='auto')
    Out[9]: <matplotlib.figure.Figure at 0x103c9fe90>

    In [10]: rt.make_raw(20)  # Applies ICA automatically.
    Out[10]: <RawArray  |  None, n_channels x n_times : 33 x 2000 (20.0 sec),
    ~588 kB, data loaded>

    In [11]: # One can make a function that performs the necessary analyses.
    This function can be called every time a buffer of EEG data reaches a
    user-defined size.
    """


    def __init__(self):
        self.active_streams = {
            'eeg': False,
            'markers': False,
        }
        self._stream_inlet_objects = {
            'eeg': None,
            'markers': None,
        }
        self._threads = {
            'eeg': None,
            'markers': None,
        }
        self._thread_locks = {
            'eeg': RLock(),
            'markers': RLock(),
        }
        self._kill_signals = {
            'eeg': Event(),
            'markers': Event(),
        }
        self._disconnected_streams = {
            'eeg': False,
            'markers': False,
        }

        self.t0 = 0

        self._eeg_data = []
        self._marker_data = []

        self.info = None
        self.ica = ICA(method='extended-infomax')
        self.raw_for_ica = None

    def _check_if_stream_active(self, type_):
        """Check whether a stream is currently active.

        Parameters
        ----------
        type_ : {'EEG', 'Markers'} (case-insensitive)
            The stream to check.
        """
        if type_.lower() == 'eeg':
            active = self.active_streams['eeg'] or bool(self._eeg_data)
            if not active:
                raise RuntimeError("EEG stream not yet started or EEG data is "
                                   "empty.")
        elif type_.lower() == 'markers':
            active = self.active_streams['markers'] or bool(self._marker_data)
            if not active:
                raise RuntimeError("Markers stream not yet started or marker "
                                   "data is empty.")
        return True

    def available_streams(self):
        """Return list of all available LabStreamingLayer streams.

        Should ContinuousResolver be used here instead?
        """
        return resolve_streams()

    def recording_duration(self):
        """Return duration of recording in seconds.

        Returns
        -------
        data_time : float
            Recording duration, calculated by n_samples / sfreq.
        """
        self._check_if_stream_active('eeg')
        return len(self._eeg_data) / float(self.info['sfreq'])

    def _connect(self, type_, lsl_predicate, data, lock, kill_signal,
                 eeg_sfreq):
        """Connect to stream and collect data.

        Parameters
        ----------
        type_ : {'EEG', 'Markers'} (case-insensitive)
            The type of stream to connect to. If "EEG" is passed, will also get
            sampling rate and channel names of the EEG data.
        lsl_predicate : str
            # TODO: add information about the predicate.
        data : list
            List to which data is appended.
        lock : threading.RLock
            Thread lock used by the desired stream.
        """
        inlet = _get_stream_inlet(type_=type_, lsl_predicate=lsl_predicate)

        self._stream_inlet_objects[type_.lower()] = inlet

        self.active_streams[type_.lower()] = True
        self.t0 = time.time()

        # Get EEG metadata if connecting to an EEG stream.
        if type_.lower() == 'eeg':
            root = ET.fromstring(inlet.info().as_xml())

            if eeg_sfreq is None:
                try:
                    sfreq = float(root.find('nominal_srate').text)
                except AttributeError:
                    raise ValueError("Could not find sampling frequency. "
                                     "Please specify sampling frequency in the "
                                     "parameter eeg_sfreq.")
            # Add error handling here.

            # Get channel names from stream meta-data.
            # Make this more generic...
            ch_names = [ch.find('name').text for ch in
                        root.findall('./desc/channel')]

            if not ch_names:
                warnings.warn("There are zero channels in the EEG stream.")

            # Add stim channel.
            ch_types = ['eeg' for __ in ch_names] + ['stim']
            ch_names.append('STI 014')

            self.info = create_info(ch_names=ch_names,
                                    sfreq=sfreq, ch_types=ch_types,
                                    montage=self.eeg_montage)

            # Add time of recording.
            # List of POSIX timestamp, number of microseconds.
            d = datetime.datetime.now()
            timestamp = time.mktime(d.timetuple())
            self.info['meas_date'] = [timestamp, 0]

        _grab_data_indefinitely(inlet, data, lock, kill_signal)
        return None

    def connect(self, eeg=True, markers=False, eeg_predicate=None,
                markers_predicate=None, eeg_montage=None, eeg_sfreq=None):
        """Start streaming EEG data and/or markers.

        This function starts daemon thread(s) of EEG data and/or marker data.
        Being daemons, the threads will exit once the main program exits.

        Parameters
        ----------
        eeg : bool (defaults to True)
            If True, attempts to connect to a LSL stream of type 'EEG' and
            begins to record EEG data to the list self._eeg_data once connected.
            To access the EEG data, use the class method _get_raw_eeg_data().
        markers : bool (defaults to False)
            If True, attempts to connect to a LSL stream of type Markers and
            beings to record marker data to the list self._marker_data once
            connected. To load the markers into a script, use the class method
            make_events().
        eeg_predicate : str
            # TODO: Add information about the predicate.
        markers_predicate : str
            # TODO: Add information about the predicate.
        eeg_montage : str
            The electrode montage to use. See mne.channels.Montage.
        eeg_sfreq : int, float
            The EEG sampling frequency. If this value cannot be found in the LSL
            stream metadata, the sampling frequency can be supplied in this
            parameter.
        """
        if eeg:
            if not self.active_streams['eeg']:
                # Add the EEG montage (channel locations).
                self.eeg_montage = eeg_montage
                self._threads['eeg'] = Thread(
                    target=self._connect, args=(
                        'EEG', eeg_predicate, self._eeg_data,
                        self._thread_locks['eeg'], self._kill_signals['eeg'],
                        eeg_sfreq),
                    name="EEG-data")
                self._threads['eeg'].daemon = True
                self._threads['eeg'].start()
            else:
                warnings.warn("EEG stream already active.")

        if markers:
            if not self.active_streams['markers']:
                self._threads['markers'] = Thread(
                    target=self._connect, args=(
                        'Markers', markers_predicate, self._marker_data,
                        self._thread_locks['markers'],
                        self._kill_signals['markers'], None),
                    name="Markers-data")
                self._threads['markers'].daemon = True
                self._threads['markers'].start()
            else:
                warnings.warn("Markers stream already active.")

        if not eeg and not markers:
            raise RuntimeError("Not trying to connect to any streams because "
                               "EEG and Markers were both set to False.")
        return None

    def disconnect(self):
        """Closes LSL StreamInlet for EEG and/or Markers data and stops
        collecting data (but does not delete the data). This does not stop the
        threads. They will exit once the program exits.
        """
        for type_ in ['eeg', 'markers']:
            # Only disconnect if the stream is active.
            if self.active_streams[type_]:
                # Close the StreamInlet.
                self._stream_inlet_objects[type_].close_stream()

                # Indicate that the stream_type is inactive and disconnected.
                self.active_streams[type_] = False
                self._disconnected_streams[type_] = True

                # # Exit while-loop of data acquisition.
                # self._kill_signals[this_type_.lower()].set()
        return self.active_streams

    def reconnect(self):
        """Reconnect to a stream after disconnecting.

        Reconnecting to stream does not seem to work. Why?
        """
        for type_ in ['eeg', 'markers']:
            # Only reconnect if the stream was disconnected.
            if self._disconnected_streams[type_]:
                # Reopen the StreamInlet.
                self._stream_inlet_objects[type_].open_stream()
                # Indicate that the stream_type is active and reconnected.
                self.active_streams[type_] = True
                self._disconnected_streams[type_] = False

        return self.active_streams

    # def time_correction(self, type_):
    #     """Retrieve an estimated time correction offset for the given stream.
    #
    #     This comes from LabStreamingLayer.
    #     """
    #     if type_.lower() not in ['eeg', 'markers']:
    #         raise ValueError("`type_` must be 'EEG', 'Markers', or None. "
    #                          "'{}' was passed".format(type_))
    #
    #     self._check_if_stream_active(type_.lower())
    #
    #     return self._stream_inlet_objects[type_.lower()].time_correction()

    def eeg_latency(self):
        """Return the latency of the EEG recording in seconds. This is
        calculated by taking the difference between this machine's clock and the
        last EEG timestamp.

        Questions
        ---------
        - Is the RLock necessary here?
        """
        self._check_if_stream_active('eeg')
        with self._thread_locks['eeg']:
            return local_clock() - self._eeg_data[-1][-1]

    def _get_raw_eeg_data(self, data_duration=None):
        """Get data from the EEG data thread. This also returns the timestamps.

        Parameters
        ----------
        data_duration : int
            Window of data to output in seconds. If None, will return all of
            the EEG data.

        Returns
        -------
        data : array
            Array of EEG data with shape (n_channels + timestamp, n_samples)
        """
        # Raises error if stream has not been started yet.
        self._check_if_stream_active('EEG')

        if data_duration is not None:
            index = int(data_duration * self.info['sfreq'])
            _check_data_index(index, self._eeg_data)
            with self._thread_locks['eeg']:
                d = [row[:] for row in self._eeg_data[-index:]]
        else:
            with self._thread_locks['eeg']:
                d = [row[:] for row in self._eeg_data]

        d = np.array(d, dtype=np.float64).T

        # Scale the EEG data (but not timepoints) for Enobio32.
        d[:-1,:] = np.divide(d[:-1,:], 1000000)
        return d

    def make_events(self, data, event_duration=0):
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
        event_duration : int (defaults to 0)
            Duration of each event marker in seconds. This is not epoch
            duration.

        Returns
        -------
        events : ndarray
            Array of events in the shape (n_events, 3).
        """
        # Raises error if stream has not been started yet.
        self._check_if_stream_active("Markers")

        # Get the marker data and convert to ndarray.
        lower_time_limit = data[-1,0]
        upper_time_limit = data[-1,-1]
        with self._thread_locks['markers']:
            tmp = [row[:] for row in self._marker_data
                   if upper_time_limit >= row[-1] >= lower_time_limit]
        tmp = np.array(tmp, dtype=np.int32)

        # Pre-allocate array for speed.
        events = np.zeros(shape=(tmp.shape[0], 3), dtype=np.int32)
        event_index = 0
        # If there is at least one marker...
        if tmp.shape[0] > 0:
            for marker_int, timestamp in tmp:
                # Get the index where this marker happened in the EEG data.
                eeg_index = (np.abs(data[-1,:] - timestamp)).argmin()
                # Add a row to the events array.
                events[event_index, :] = eeg_index, event_duration, marker_int
                event_index += 1
        else:
            # Make empty events array.
            events = np.array([[0, 0, 0]])

        return events


    def make_raw(self, data=None, info=None, apply_ica=True, first_samp=0,
                 verbose=None):
        """Create instance of mne.io.RawArray.

        Parameters
        ----------
        data : int, float
            Duration of previous data to use. If data=10, returns instance of
            mne.io.RawArray of the previous 10 seconds of data.
        info : mne.Info
            The measurement info. Stored in the attribute info.
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
        raw_data = self._get_raw_eeg_data(data)

        if info is None:
            info = self.info

        # Add events if Markers stream was started.
        if self.active_streams['markers']:
            raw = io.RawArray(raw_data, info, first_samp=first_samp,
                              verbose=verbose)
            events = self.make_events(raw_data)
            raw_data[-1,:] = 0  # Replace timestamps with zeros.
            raw.add_events(events)
        else:
            raw_data[-1,:] = 0  # Make row of timestamps a row of events 0.
            raw = io.RawArray(raw_data, info, first_samp=first_samp,
                              verbose=verbose)

        # If user wants to apply ICA and if ICA has been fitted ...
        if apply_ica and self.ica.current_fit != 'unfitted':
            return self.ica.apply(raw)

        return raw


    def make_epochs(self, data=None, events=None, event_duration=0,
                    event_id=None, apply_ica=True, tmin=-0.2, tmax=1.0,
                    baseline=(None, 0), picks=None, name='Unknown',
                    preload=False, reject=None, flat=None, proj=True, decim=1,
                    reject_tmin=None, reject_tmax=None, detrend=None,
                    add_eeg_ref=None, on_missing='error',
                    reject_by_annotation=True, verbose=None):
        """Create instance of mne.Epochs. If events are not supplied, this
        script must be connected to a Markers stream.

        Parameters
        ----------
        data : int
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
        raw_data = self._get_raw_eeg_data(data)

        if events is None:
            events = self.make_events(raw_data, event_duration=event_duration)

        raw_data[-1,:] = 0
        raw = io.RawArray(raw_data, self.info)

        # If user wants to apply ICA and if ICA has been fitted ...
        if apply_ica and self.ica.current_fit != 'unfitted':
            raw = self.ica.apply(raw)

        epochs = Epochs(raw, events, event_id=event_id, tmin=tmin, tmax=tmax,
                        baseline=baseline, picks=picks,name=name,
                        preload=preload, reject=reject, flat=flat, proj=proj,
                        decim=decim, reject_tmin=reject_tmin,
                        reject_tmax=reject_tmax, detrend=detrend,
                        add_eeg_ref=add_eeg_ref, on_missing=on_missing,
                        reject_by_annotation=reject_by_annotation,
                        verbose=verbose)

        return epochs


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
        # Raises error if stream has not been started yet.
        self._check_if_stream_active('EEG')

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
                end_index = len(self._eeg_data)
                start_index = end_index - user_index
                # Warns if index is out of bounds.
                _check_data_index(user_index, self._eeg_data)

            elif when == 'next':
                start_index = len(self._eeg_data)
                end_index = start_index + user_index

                # Wait until the data is available.
                pbar = ProgressBar(end_index - start_index,
                                   mesg="Collecting data")
                while len(self._eeg_data) <= end_index:
                    # Sometimes sys.stdout.flush() raises ValueError. Is it
                    # because the while-loop iterates too quickly for I/O?
                    try:
                        pbar.update(len(self._eeg_data) - start_index)
                    except ValueError:
                        pass
                print('')

            with self._thread_locks['eeg']:
                d = [r[:] for r in self._eeg_data[start_index:end_index]]
            _data = np.array(d).T

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
        self.ica.fit(self.raw_for_ica)
        print("Finished in {:.2f} s".format(local_clock() - t0))

        return self.ica


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
            raise RuntimeError("ICA has not yet been fitted or data used to "
                               "fit ICA no longer exists. Fit ICA before "
                               "calling this function again.")

        if plot == 'components':
            return self.ica.plot_sources(self.raw_for_ica)

        elif plot == 'map_components':
            return self.ica.plot_components()

        elif plot == 'cleaned_data':
            if not self.ica.exclude:
                warnings.warn("No ICA components were marked for removal. EEG "
                              "data has not been changed.")
            print(self.ica.exclude)
            return self.ica.apply(self.raw_for_ica.copy()).plot()
