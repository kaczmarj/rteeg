"""Base class for recording streams of data."""
# Author: Jakub Kaczmarzyk <jakubk@mit.edu>
from __future__ import division, print_function, absolute_import
import collections
import threading

from rteeg.utils import logger


class BaseStream(object):
    """Base class for recording streams of data."""
    def __init__(self):
        self._active = False
        self._kill_signal = threading.Event()
        self.data = ThreadSafeList()

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
        if self._active:
            raise RuntimeError("Stream already active.")
        self._thread = threading.Thread(target=target, name=name)
        self._thread.daemon = True
        self._thread.start()

    def copy_data(self, index=None):
        """Return deep copy `self.data`.

        Parameters
        ----------
        index : int
            Return last `index` items. By default, returns all items.
        """
        if index is None:
            return [row[:] for row in self.data]
        else:
            current_max = len(self.data)
            if index > current_max:
                logger.warning("Last {} samples were requested, but only {} "
                               "are present.".format(index, current_max))
            return [row[:] for row in self.data[-index:]]


class ThreadSafeList(collections.MutableSequence):
    """Thread-safe list class.

    This class subclasses collections.MutableSequence and is not completely
    thread-safe. Only the methods that incorporate a thread lock will be
    thread-safe, and only the methods that are relevant to this package
    incorporate thread locks. For example, the __iter__ and __getitem__ methods
    are thread-safe, which allows for thread-safe read/write of data.

    FYI:
    >>> dir(MutableSequence)
    ['__abstractmethods__', '__class__', '__contains__', '__delattr__',
    '__delitem__', '__dict__', '__doc__', '__format__', '__getattribute__',
    '__getitem__', '__hash__', '__iadd__', '__init__', '__iter__', '__len__',
    '__metaclass__', '__module__', '__new__', '__reduce__', '__reduce_ex__',
    '__repr__', '__reversed__', '__setattr__', '__setitem__', '__sizeof__',
    '__str__', '__subclasshook__', '__weakref__', '_abc_cache',
    '_abc_negative_cache', '_abc_negative_cache_version', '_abc_registry',
    'append', 'count', 'extend', 'index', 'insert', 'pop', 'remove', 'reverse']

    Made with help from:
        <http://stackoverflow.com/a/3488283/5666087>
        <http://stackoverflow.com/a/23617436/5666087>
    """
    def __init__(self, iterable=None):
        if iterable is None:
            self._list = list()
        else:
            self._list = list(iterable)
        self.rlock = threading.RLock()

    def __len__(self): return len(self._list)

    def __str__(self): return str(self._list)

    def __repr__(self):
        return "{self.__class__.__name__}({self._list})".format(self=self)

    def __getitem__(self, i):
        with self.rlock:
            return self._list[i]

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
