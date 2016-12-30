"""Author: Jakub Kaczmarzyk, jakubk@mit.edu"""
from threading import Event, RLock, Thread
import warnings

from pylsl import resolve_streams

warnings.filterwarnings(action='always', module='rteeg')

def resolve_streams():
    """Return list of available LabStreamingLayer streams."""
    return resolve_streams()


class BaseStream(object):

    def __init__(self, ):
        self._thread_lock = RLock()
        self._kill_signal = Event()
        self.data = []

    def __del__(self):
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
            with self._thread_lock:
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
        self._thread = Thread(target=target, name=name)
        self._thread.daemon = True
        self._thread.start()

    def copy_data(self, index=0):
        """Copy `data` in a thread-safe manner.

        Parameters
        ----------
        index : int
            Get last `index` items. By default, returns all items.
        """
        current_max = len(self.data)
        if index > current_max:
            warnings.warn("Last {} samples were requested, but only {} are "
                          "present.".format(index, current_max))
        with self._thread_lock:
            return [row[:] for row in self.data[-index:]]
