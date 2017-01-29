"""Tests for rteeg.analysis.py"""
# Author: Jakub Kaczmarzyk <jakubk@mit.edu>
from __future__ import division, print_function, absolute_import

import sys
import threading
import time

from rteeg.analysis import LoopAnalysis, MainWindow
from rteeg.stream import EEGStream
from rteeg.tests.utils import SyntheticData

def test_LoopAnalysis():
    """Test of rteeg.analysis.LoopAnalysis"""
    # Create outlet of EEG data.
    eeg_1 = SyntheticData("EEG", 32, 100, send_data=True)
    # Receive the stream of EEG data.
    eeg = EEGStream(key='default')
    time.sleep(5.)
    # Define analysis function.
    list_ = []  # Append to this list with each call; query len after end of loop.
    def analysis_func(arg):
        list_.append(arg)

    interval = 2.
    loop = LoopAnalysis(eeg, buffer_len=interval, func=analysis_func,
                        args=('test',), show_window=False)

    # Test loop with show_window=False.
    total_analysis_time = 11.  # Run loop for this amount of time.
    list_len = total_analysis_time // interval  # What the len of list_ should be.
    loop.start()
    time.sleep(total_analysis_time)
    loop.stop()
    print(len(list_))
    assert len(list_) == list_len, "Analysis function called incorrect # of times."

    # Attempt to test GUI. This might fail.
    # window = MainWindow(loop.stream, loop.func, loop.args, loop.buffer_len,
    #                     loop._kill_signal)

    # Clean up.
    eeg_1.stop()
