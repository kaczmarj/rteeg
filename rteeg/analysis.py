"""Apply a machine learning model to EEG data.

The analysis messes up if there is a delay in transmission between the EEG
hardware and Coregui. Is there any way around that? Can we check whether the
list of markers changed in size? Not only if it changes in size but if the
timestamp is somewhere inside the EEG data.

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


Instead of starting a regular Python thread, should we start a QThread? That
might make it easier to update the feedback GUI.


Add a function that will display a feedback window so the user can design and
debug their feedback window.
"""
import sys
from threading import Event, Thread
import time
from warnings import warn

from PyQt4 import QtGui, QtCore

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
                 show_window=False, n_iterations=None, n_seconds=None):
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
        show_window : bool (defaults to False)
            If True, shows a PyQt window with whatever is returned by
            `analysis_func`.
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
        self.show_window = show_window
        self.n_iterations = n_iterations
        self.n_seconds = n_seconds

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
            t0 = self.stream.recording_duration()
            while not self._kill_signal.is_set():
                if len(self.stream._eeg_data) - b0 >= self.buffer_len:
                    b0 = len(self.stream._eeg_data)
                    self.analysis_func(*self.analysis_args)
                if self.stream.recording_duration() - t0 > self.n_seconds:
                    self.stop()
                time.sleep(sleep_time)


    def _loop_analysis_show_window(self):
        """Show feedback window. This window updates the feedback at an interval
        defined by the user.

        If this function is called, `func` must return a string to be displayed
        in the feedback window. This string can include HTML and CSS, though not
        all CSS is supported. See PyQt's stylesheet.

        Parameters
        ----------
        stream : rteeg.Stream
            The stream to which you are connected.
        func : function
            Function to be run on each chunk of data.
        analysis_args : tuple
            Arguments for `func`.
        """
        app = QtGui.QApplication.instance()
        if not app:
            app = QtGui.QApplication(sys.argv)
        self.window = MainWindow(self.stream, self.analysis_func,
                                 self.analysis_args, self.buffer_len,
                                 self._kill_signal, self.n_iterations,
                                 self.n_seconds)
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
                 n_iterations=None, n_seconds=None, parent=None):
        super(MainWindow, self).__init__(parent)

        self.stream = stream
        self.func = func
        self.args = args
        self.buffer_len = buffer_len
        self.kill_signal = kill_signal
        self.n_iterations = n_iterations
        self.n_seconds = n_seconds


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
                             kill_signal=self.kill_signal,
                             n_iterations=self.n_iterations,
                             n_seconds=self.n_seconds)
        self.worker.beep.connect(self.update)
        self.worker.start()


    def update(self, text):
        self.feedback.setText(text)



class Worker(QtCore.QThread):
    """Updates feedback in separate QThread."""
    beep = QtCore.pyqtSignal(str)


    def __init__(self, stream, func, args, buffer_len, kill_signal,
                 n_iterations=None, n_seconds=None, parent=None):
        super(Worker, self).__init__(parent)

        self.stream = stream
        self.func = func
        self.args = args
        self.buffer_len = buffer_len
        self._kill_signal = kill_signal
        self.n_iterations = n_iterations
        self.n_seconds = n_seconds

        self.running = False


    def run(self):
        self.running = True

        sleep_time = 0.001  # Time to sleep between querying len(list).
        b0 = len(self.stream._eeg_data)

        while self.running:

            if self.n_iterations is None and self.n_seconds is None:
                if len(self.stream._eeg_data) - b0 >= self.buffer_len:
                    b0 = len(self.stream._eeg_data)
                    output = self.func(*self.args)
                    self.beep.emit(output)
                time.sleep(sleep_time)

            elif self.n_iterations is not None:
                i = 0
                if i >= self.n_iterations:
                    self.stop()
                elif len(self.stream._eeg_data) - b0 >= self.buffer_len:
                    b0 = len(self.stream._eeg_data)
                    output = self.func(*self.args)
                    self.beep.emit(output)
                    i += 1
                time.sleep(sleep_time)

            elif self.n_seconds is not None:
                t0 = self.stream.recording_duration()
                if self.stream.recording_duration() - t0 > self.n_seconds:
                    self.stop()
                elif len(self.stream._eeg_data) - b0 >= self.buffer_len:
                    b0 = len(self.stream._eeg_data)
                    output = self.func(*self.args)
                    self.beep.emit(output)
                time.sleep(sleep_time)


    def stop(self):
        self.running = False


    def update_value(self, value):
        self.feedback = value
