"""Apply a machine learning model to EEG data.

The analysis messes up if there is a delay in transmission between the EEG
hardware and Coregui. Is there any way around that? Can we check whether the
list of markers changed in size? Not only if it changes in size but if the
timestamp is somewhere inside the EEG data.

Potential ways to account for latency:
    1. Get latency and sleep for that amount before starting analysis.
    2. In addition to (1), account for changes in latency by sleeping any added
        latency right before calling the function.
    3. Get latency and sleep for that amount right before calling the function.
    4. Use the timestamps. Get current time, and then return function once
        data has timestamp with current time + buffer_len.

OR we could:
    1. Inform the user that the Wifi connection must be strong for this module
        to work with Enobio32.
    2. Alert user when latency goes above a threshold.

If we wanted to create a model and apply it within the same experiment, how
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

TODO
----
1. Add a function that will display a feedback window so the user can design and
    debug their feedback window.
2. Remove support for n_iterations and n_seconds. It is unnecessary.
"""
import sys
from threading import Event, Thread
import time
from warnings import warn

from pylsl import local_clock
from PyQt4 import QtGui, QtCore

from .stream import Stream


def _get_latest_timestamp(stream):
    """Get the last recorded timestamp from rteeg.Stream object."""
    with stream._thread_locks['eeg']:
        return stream._eeg_data[-1][-1]

def _loop_worker(stream, func, args, buffer_len, kill_signal, show_window,
                pyqt_signal=None):
    """Call `func(*args)` each time `stream._eeg_data` increases by
    `buffer_len`.

    Parameters
    ----------
    stream : rteeg.Stream
        Stream of EEG data or event markers.
    func : function
        The function to be called everytime the length of the buffer reaches
        `buffer_len`.
    args : tuple
        Arguments to pass to `func`.
    buffer_len : int
        The length of the buffer in number of samples.
    kill_signal
        If `show_window` is False, `kill_signal` must be threading.Event. If
        `show_window` is True, `kill_signal` must be QThread method.
    show_window : bool
        Whether or not PyQt window is shown. If True, will emit `pyqt_signal`
        to refresh PyQt window.
    pyqt_signal : pyqt.QtCore.pyqtSignal
        Signal which, when emitted, will change text on the PyQt window.
    """
    SLEEP_TIME = 0.001  # Time to sleep between buffer_len queries.
    t0 = local_clock()

    if show_window:
        while not kill_signal:
            t1 = _get_latest_timestamp(stream)
            if t1 - t0 >= buffer_len:
                t0 = t1
                # Refresh PyQt window with whatever `func` returns.
                pyqt_signal.emit(func(*args))  # `func` must return str.
            time.sleep(SLEEP_TIME)
    else:
        while not kill_signal.is_set():
            t1 = _get_latest_timestamp(stream)
            if t1 - t0 >= buffer_len:
                t0 = t1
                func(*args)
            time.sleep(SLEEP_TIME)



class LoopAnalysis(object):
    """Class to loop analysis of EEG data every time a buffer of some length
    becomes full.

    The temporal precision of this function has not been measured, but it is
    not recommended to use this function with something that requires
    high precision (e.g., ERP analysis) without the use of markers.

    Include use example here.

    Parameters
    ----------
    stream : rteeg.Stream
        The stream to which you are connected.
    buffer_len : int, float
        The length of the buffer in seconds. This is translated to number
        of samples by multiplying buffer_len by the EEG sampling rate.
    func : function
        The function to be called everytime the length of the buffer reaches
        buffer_len.
    args : tuple
        Arguments to pass to `func`.
    show_window : bool (defaults to False)
        If True, shows a PyQt window with whatever is returned by
        `func`.
    n_iterations : int
        If not None, stop the analysis after `n_iterations` iterations.
    n_seconds : int, float
        If not None, stop the analysis after `n_seconds` seconds have
        passed. Ignore if n_iterations is not None.
    """

    def __init__(self, stream, buffer_len, func, args=(),
                 show_window=False, n_iterations=None, n_seconds=None):
        if type(stream) is not Stream:
            raise TypeError("Stream must be type `rteeg.stream.Stream`. {} "
                            "was passed.".format(type(stream)))

        if type(buffer_len) is not int and type(buffer_len) is not float:
            raise TypeError("buffer_len must be type int or float. {} was "
                            "passed.".format(type(buffer_len)))

        if not callable(func):
            raise TypeError("Function must be a Python callable.")

        if type(args) is not tuple:
            raise TypeError("args must of type `tuple`. {} was passed."
                            "".format(type(args)))

        if n_iterations is not None and n_seconds is not None:
            warn("n_iterations and n_seconds were both specified. n_seconds "
                 "will be ignored.")

        self.stream = stream
        # Raise error if EEG stream not yet active.
        self.stream._check_if_stream_active('EEG')

        self.buffer_len = buffer_len  # * stream.info['sfreq']
        self.func = func
        self.args = args
        self.show_window = show_window

        self.analysis_active = False
        self._kill_signal = Event()

        if not self.show_window:
            # Start the analysis loop in another thread.
            self._loop_analysis_thread = Thread(target=self._loop_analysis,
                                                name="Analysis-loop")
            self._loop_analysis_thread.daemon = True
            self._loop_analysis_thread.start()

        else:
            self._loop_analysis_show_window()

    def _loop_analysis(self):
        """Call a function every time a buffer reaches `self.buffer_len`."""
        self.analysis_active = True

        _loop_worker(stream=self.stream, func=self.func, args=self.args,
                     buffer_len=self.buffer_len, kill_signal=self._kill_signal,
                     show_window=self.show_window)

    def _loop_analysis_show_window(self):
        """Show feedback window. This window updates the feedback at an interval
        defined by the user.

        If this function is called, `func` must return a string to be displayed
        in the feedback window. This string can include HTML and CSS, though not
        all CSS is supported. See PyQt's stylesheet.
        """
        app = QtGui.QApplication.instance()
        if not app:
            app = QtGui.QApplication(sys.argv)
        self.window = MainWindow(self.stream, self.func,
                                 self.args, self.buffer_len,
                                 self._kill_signal)
        self.window.show()
        # Stop the AnalysisLoop if MainWindow is closed.
        app.aboutToQuit.connect(self.stop)
        sys.exit(app.exec_())

    def stop(self):
        """Stop the analysis loop."""
        self._kill_signal.set()
        self.analysis_active = False

        if self.show_window:
            self.window.worker.stop()

        print("Loop of analysis stopped.")



class MainWindow(QtGui.QWidget):
    """Window that displays feedback."""
    def __init__(self, stream, func, args, buffer_len, kill_signal,
                 parent=None):
        super(MainWindow, self).__init__(parent)

        self.stream = stream
        self.func = func
        self.args = args
        self.buffer_len = buffer_len
        self.kill_signal = kill_signal

        self.feedback = QtGui.QLabel()
        self.feedback.setText("Waiting for feedback ...")
        self.feedback.setAlignment(QtCore.Qt.AlignCenter)

        self.font = QtGui.QFont()
        self.font.setPointSize(24)
        self.feedback.setFont(self.font)

        self.layout = QtGui.QVBoxLayout()
        self.layout.addWidget(self.feedback)

        self.setLayout(self.layout)
        self.setWindowTitle("feedback")
        self.resize(300, 200)

        self.worker = Worker(stream=self.stream,
                             func=self.func,
                             args=self.args,
                             buffer_len=self.buffer_len,
                             kill_signal=self.kill_signal)
        self.worker.refresh_signal.connect(self.update)
        self.worker.start()

    def update(self, text):
        self.feedback.setText(text)



class Worker(QtCore.QThread):
    """Updates feedback in separate QThread."""
    refresh_signal = QtCore.pyqtSignal(str)

    def __init__(self, stream, func, args, buffer_len, kill_signal,
                 parent=None):
        super(Worker, self).__init__(parent)

        self.stream = stream
        self.func = func
        self.args = args
        self.buffer_len = buffer_len
        self._kill_signal = kill_signal
        self.stopped = True

    def run(self):
        self.stopped = False
        _loop_worker(stream=self.stream, func=self.func, args=self.args,
                     buffer_len=self.buffer_len, kill_signal=self.stopped,
                     show_window=True, pyqt_signal=self.refresh_signal)

    def stop(self):
        self.stopped = True

    def update_value(self, value):
        self.feedback = value
