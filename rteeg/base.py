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
        self.data = []

    def __del__(self):
        # Break out of the loop of data collection.
        self._kill_signal.set()

    def _update(self, row):
        self.data.append(row)

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
            self._update(sample)

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
        else:
            self._thread = threading.Thread(target=target, name=name)
            self._thread.daemon = True
            self._thread.start()
            self._active = True

    def copy_data(self, index=None):
        """Return deep copy `self.data`.

        Parameters
        ----------
        index : int
            Return last `index` items. By default, returns all items.
        """
        if index is None:
            # Make this a numpy array?
            tmp = self.data[:]  # Shallow copy.
            return [row[:] for row in tmp]  # Deep copy.
        else:
            current_max = len(self.data)
            tmp = self.data[-index:]  # Shallow copy.
            if index > current_max:
                logger.warning("Last {} samples were requested, but only {} "
                               "are present.".format(index, current_max))
            return [row[:] for row in tmp]  # Deep copy.
