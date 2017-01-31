"""Tests for rteeg.analysis.py"""
# Author: Jakub Kaczmarzyk <jakubk@mit.edu>
from __future__ import division, print_function, absolute_import

import sys
import threading
import time

from PyQt5.QtWidgets import QApplication

from rteeg import EEGStream, LoopAnalysis
from rteeg.analysis import MainWindow
from rteeg.tests.utils import SyntheticData

list_ = []  # Append to this list with each call; query len after end of loop.
def func(arg):
    list_.append(arg)
    return "TEST {}".format(len(list_))

def test_LoopAnalysis():
    """Test of rteeg.analysis.LoopAnalysis"""
    # Create outlet of EEG data.
    eeg_1 = SyntheticData("EEG", 32, 100, send_data=True)
    # Receive the stream of EEG data.
    eeg = EEGStream(key='default')
    time.sleep(5.)
    # Define analysis function.

    interval = 2.
    loop = LoopAnalysis(eeg, buffer_len=interval, func=func,
                        args=('test',), show_window=False)

    # Test loop with show_window=False.
    total_analysis_time = 11.  # Run loop for this amount of time.
    list_len = total_analysis_time // interval  # What the len of list_ should be.
    loop.start()
    time.sleep(total_analysis_time)
    loop.stop()
    print(len(list_))
    assert len(list_) == list_len, "Analysis function called incorrect # of times."

    # Clean up.
    eeg_1.stop()

def test_MainWindow():
    eeg_1 = SyntheticData("EEG", 32, 100, send_data=True)
    eeg = EEGStream()
    time.sleep(5.)  # Wait to find stream.

    event = threading.Event()
    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)

    # Instantiate window.
    window = MainWindow(eeg, func, (), 2, event)
    window.show()
    time.sleep(5.)  # Will sleeping allow the loop worker to work?

    # Clean up.
    eeg_1.stop()
