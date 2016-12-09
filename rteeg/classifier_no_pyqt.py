"""Apply a machine learning model to EEG data.

We will use a pre-existing model.

But if we wanted to create a model and apply it within the same experiment, how
could that be done?
    Have a model training block of trials at the beginning, and once the block
    is over, get the data and event markers from that block. Take all the data
    and make epochs using those events (that way, we are sure we are not
    discarding good data). Preprocess accordingly (filter, ICA), and then
    extract the features (e.g., first 15 PCA components of power spectral
    density output). Cross validate to check model performance, and then train
    the model with all of the data. Save the model as an object in the class,
    and predict each upcoming trial. But before each prediction, must filter,
    apply ICA, and extract features.


Instead of starting a regular Python thread, should we start a QThread? That
might make it easier to update the feedback GUI.
"""
from threading import Event, Thread
import time
from warnings import warn

from .stream import Stream



class LoopAnalysis(object):
    """Class to loop analysis of EEG data every time a buffer of some length
    becomes full.

    The temporal precision of this function has not been measured, but it is
    not recommended to use this function with something that requires
    high precision (e.g., ERP analysis) without the use of markers.

    Include use example here.
    """

    def __init__(self, stream, buffer_len, analysis_func, analysis_args=(),
                 n_iterations=None, n_seconds=None):
        """Call an analysis function once a buffer of some size becomes full.

        Parameters
        ----------
        stream : rteeg.Stream
            The stream to which you are connected.
        buffer_len : int, float
            The length of the buffer in seconds. This is translated to number
            of samples by multiplying buffer_len by the EEG sampling rate.
        analysis_func : function
            The function to be called everytime the length of the buffer reaches
            buffer_len.
        analysis_args : tuple
            Arguments to pass to `func`.
        n_iterations : int
            If not None, stop the analysis after `n_iterations` iterations.
        n_seconds : int, float
            If not None, stop the analysis after `n_seconds` seconds have
            passed. Ignore if n_iterations is not None.
        """
        if type(stream) is not Stream:
            raise TypeError("Stream must be type `rteeg.stream.Stream`. {} "
                            "was passed.".format(type(stream)))

        if type(buffer_len) is not int and type(buffer_len) is not float:
            raise TypeError("buffer_len must be type int or float. {} was "
                            "passed.".format(type(buffer_len)))

        if not callable(analysis_func):
            raise TypeError("Function must be a function. Something not "
                            "callable was passed.")

        if type(analysis_args) is not tuple:
            raise TypeError("args must of type `tuple`. {} was passed."
                            "".format(analysis_args))

        if n_iterations is not None and n_seconds is not None:
            warn("n_iterations and n_seconds were both specified. n_seconds "
                 "will be ignored.")

        self.stream = stream
        # Raise error if EEG stream not yet active.
        self.stream._check_if_stream_active('EEG')

        # Convert to n_samples from time (seconds)
        self.buffer_len = buffer_len * stream.info['sfreq']

        self.analysis_func = analysis_func
        self.analysis_args = analysis_args
        self.n_iterations = n_iterations
        self.n_seconds = n_seconds

        self.analysis_active = False
        self._kill_signal = Event()

        # Start the analysis loop in another thread.
        self._loop_analysis_thread = Thread(target=self._loop_analysis,
                                            name="Analysis-loop")
        self._loop_analysis_thread.daemon = True
        self._loop_analysis_thread.start()


    def _loop_analysis(self):
        """Call a function every time a buffer reaches a certain length
        (defined by `self.buffer_len`).
        """
        self.analysis_active = True
        sleep_time = 0.01  # Time to sleep between querying len(list).
        b0 = len(self.stream._eeg_data)

        if self.n_iterations is None and self.n_seconds is None:
            while not self._kill_signal.is_set():
                if len(self.stream._eeg_data) - b0 >= self.buffer_len:
                    b0 = len(self.stream._eeg_data)
                    self.analysis_func(*self.analysis_args)
                time.sleep(sleep_time)

        elif self.n_iterations is not None:
            i = 0
            while not self._kill_signal.is_set():
                if i >= self.n_iterations:
                    self.stop()
                elif len(self.stream._eeg_data) - b0 >= self.buffer_len:
                    b0 = len(self.stream._eeg_data)
                    self.analysis_func(*self.analysis_args)
                    i += 1
                time.sleep(sleep_time)

        elif self.n_seconds is not None:
            print("n_seconds specified")
            t0 = self.stream.recording_duration()
            while not self._kill_signal.is_set():
                if len(self.stream._eeg_data) - b0 >= self.buffer_len:
                    b0 = len(self.stream._eeg_data)
                    self.analysis_func(*self.analysis_args)
                if self.stream.recording_duration() - t0 > self.n_seconds:
                    self.stop()
                time.sleep(sleep_time)


    def stop(self):
        """Stop the analysis loop."""
        self._kill_signal.set()
        self.analysis_active = False
