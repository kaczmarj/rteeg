# Author: Jakub Kaczmarzyk <jakubk@mit.edu>
"""Base class for recording streams of data."""
from __future__ import division, print_function
import collections
import threading
import warnings

warnings.filterwarnings(action='always', module='rteeg')


class BaseStream(object):
    """Base class for recording streams of data."""
    def __init__(self):
        self._kill_signal = threading.Event()
        self.data = ThreadSafeList()
        self.active = False

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
            self.data.append(sample)

    def connect(self, target, name):
        """Connect and record data in a separate thread.

        Parameters
        ----------
        target : callable
            The function to execute in the thread.
        name : str
            Name for the thread.

        Raises
        ------
        RuntimeError if attempting to connect more than once.
        """
        if self.active:
            raise RuntimeError("Stream already connected.")
        self._thread = threading.Thread(target=target, name=name)
        self._thread.daemon = True
        self._thread.start()
        self.active = True

    def copy_data(self, index=None):
        """Copy `data` in a thread-safe manner.

        Parameters
        ----------
        index : int
            Get last `index` items. By default, returns all items.
        """
        if index is None:
            return [row[:] for row in self.data]
        else:
            current_max = len(self.data)
            if index > current_max:
                warnings.warn("Last {} samples were requested, but only {} are "
                              "present.".format(index, current_max))
            return [row[:] for row in self.data[-index:]]



class ThreadSafeList(collections.MutableSequence):
    """Thread-safe list class.

    Go back to this to check whether more methods have to be locked.

    Made with help from:
        <http://stackoverflow.com/a/3488283/5666087>
        <http://stackoverflow.com/a/23617436/5666087>
    """
    def __init__(self, iterable=None):
        if iterable is None:
            self._list = list()
        else:
            self._list = list(iterable)
        self.rlock = RLock()

    def __len__(self): return len(self._list)

    def __str__(self): return self.__repr__()

    def __repr__(self): return str(self._list)

    def __getitem__(self, i): return self._list[i]

    def __setitem__(self, index, value):
        with self.rlock:
            self._list[index] = value

    def __delitem__(self, i):
        with self.rlock:
            del self._list[i]

    def __iter__(self):
        with self.rlock:
            for elem in self._list:
                yield elem

    def insert(self, index, value):
        with self.rlock:
            self._list.insert(index, value)
