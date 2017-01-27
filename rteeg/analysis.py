"""Classes related to analysis loops.

TODO
----
1. Add a function that will display a feedback window so the user can design and
    debug their feedback window.
"""
# Author: Jakub Kaczmarzyk <jakubk@mit.edu>
from __future__ import division, print_function, absolute_import
import numbers
import sys
from threading import Event, Thread
import time

from pylsl import local_clock
from PyQt4 import QtGui, QtCore

from rteeg.stream import EEGStream


def _get_latest_timestamp(stream):
    """Get the last recorded timestamp from rteeg.EEGStream object."""
    return stream.data[-1][-1]


def _loop_worker(stream, func, args, buffer_len, kill_signal, show_window=False,
                 pyqt_signal=None):
    """Call `func(*args)` each time `stream._eeg_data` increases by
    `buffer_len`.

    Parameters
    ----------
    stream : rteeg.EEGStream
        Stream of EEG data or event markers.
    func : function
        The function to be called everytime the length of the buffer reaches
        `buffer_len`.
    args : tuple
        Arguments to pass to `func`.
    buffer_len : int, float
        The duration of the buffer in seconds.
    kill_signal
        If `show_window` is False, `kill_signal` must be threading.Event. If
        `show_window` is True, `kill_signal` must be QThread method.
    show_window : bool
        Whether or not PyQt window is shown. If True, will emit `pyqt_signal`
        to refresh PyQt window.
    pyqt_signal : pyqt.QtCore.pyqtSignal
        Signal which, when emitted, will change text on the PyQt window.
    """
    sleep_time = 0.001  # Time to sleep between buffer_len queries.
    t_zero = local_clock()

    if show_window:
        while not kill_signal:
            # t_one = _get_latest_timestamp(stream)
            t_one = stream.data[-1][-1]
            if t_one - t_zero >= buffer_len:
                t_zero = t_one
                # Refresh PyQt window with the str that `func` returns.
                pyqt_signal.emit(func(*args))
            time.sleep(sleep_time)
    else:
        while not kill_signal.is_set():
            # t_one = _get_latest_timestamp(stream)
            t_one = stream.data[-1][-1]
            if t_one - t_zero >= buffer_len:
                t_zero = t_one
                func(*args)
            time.sleep(sleep_time)


class LoopAnalysis(object):
    """Class to loop analysis of EEG data every time a buffer of some length
    becomes full.

    The temporal precision of this function has not been measured, but it is
    not recommended to use this function with something that requires
    high precision (e.g., ERP analysis) without the use of markers.

    Include use example here.

    Parameters
    ----------
    stream : rteeg.EEGStream
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

    def __init__(self, stream, buffer_len, func, args=(), show_window=False):
        if not isinstance(stream, EEGStream):
            raise TypeError("Stream must be type `rteeg.stream.EEGStream`. {} "
                            "was passed.".format(type(stream)))
        if not isinstance(buffer_len, numbers.Number):
            raise TypeError("buffer_len must be a number. {} was passed."
                            "".format(type(buffer_len)))
        if not callable(func):
            raise TypeError("Function must be a Python callable.")
        if not isinstance(args, tuple):
            raise TypeError("args must be a tuple. {} was passed."
                            "".format(type(args)))

        self.stream = stream
        self.buffer_len = buffer_len
        self.func = func
        self.args = args
        self.show_window = show_window

        self.running = False
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
        self.running = True
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
        self.running = False

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
        """Docstring here"""
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
        self.feedback = None
        self.stopped = True

    def run(self):
        """Docstring here"""
        self.stopped = False
        _loop_worker(stream=self.stream, func=self.func, args=self.args,
                     buffer_len=self.buffer_len, kill_signal=self.stopped,
                     show_window=True, pyqt_signal=self.refresh_signal)

    def stop(self):
        """Docstring here"""
        self.stopped = True

    def update_value(self, value):
        """Docstring here"""
        self.feedback = value
