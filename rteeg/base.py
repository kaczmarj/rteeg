# Author: Jakub Kaczmarzyk <jakubk@mit.edu>
"""Base class for recording streams of data."""
from threading import Event, RLock, Thread
import warnings

warnings.filterwarnings(action='always', module='rteeg')


class BaseStream(object):
    """Base class for recording streams of data."""
    def __init__(self):
        self._thread = None
        self.thread_lock = RLock()
        self._kill_signal = Event()
        self.data = []
        self.connected = False

    def __del__(self):
        # Break out of the loop of data collection.
        self._kill_signal.set()

    def _record_data_indefinitely(self, inlet):
        """Record data to list, and correct for time differences between
        machines.

        Parameters
        ----------
        inlet : pylsl.StreamInlet
            The LabStreamingLayer inlet of data.
        """
        while not self._kill_signal.is_set():
            sample, timestamp = inlet.pull_sample()
            time_correction = inlet.time_correction()
            sample.append(timestamp + time_correction)
            with self.thread_lock:
                self.data.append(sample)

    def connect(self, target, name):
        """Connect and record data in a separate thread.

        Parameters
        ----------
        target : callable
            The function to execute in the thread.
        name : str
            Name for the thread.
        """
        if self.connected:
            raise RuntimeError("Stream already connected.")
        self._thread = Thread(target=target, name=name)
        self._thread.daemon = True
        self._thread.start()
        self.connected = True

    def copy_data(self, index=None):
        """Copy `data` in a thread-safe manner.

        Parameters
        ----------
        index : int
            Get last `index` items. By default, returns all items.
        """
        if index is None:
            with self.thread_lock:
                return [row[:] for row in self.data]
        else:
            current_max = len(self.data)
            if index > current_max:
                warnings.warn("Last {} samples were requested, but only {} are "
                              "present.".format(index, current_max))
            with self.thread_lock:
                return [row[:] for row in self.data[-index:]]
