"""PsychoPy experiment that shows a flashing checkerboard or nothing. A trigger
is sent at the beginning of each trial.

To run: open in PyschoPy Coder and press 'Run'.

TRIGGER        EVENT
--------------------
1   -->         rest
2   --> checkerboard
99  -->         test
--------------------

Parameters
----------
checkerboard size : int (defaults to 16)
    Sum of checkboard dimensions. If 16, will show 8x8 checkerboard.
flash frequency : int, float (defaults to 4)
    Frequency with which the checkerboard should flash in Hz. If 4, will switch
    checkerboards four times per second.
number of trials : int (defaults to 10)
    Total number of trials. Should be even so that the number of control
    and checkerboard trials are equal.
trial duration : int, float (defaults to 0.5)
    Duration of each trial in seconds.
inter-stimulus interval : int, float (defaults to 0.)
    Duration of inter-stimulus interval in seconds.
"""
# Author: Jakub Kaczmarzyk <jakubk@mit.edu>
from __future__ import division, print_function
import logging
import sys

import numpy as np
from pylsl import StreamInfo, StreamOutlet, local_clock
from psychopy import core, event, gui, visual

# Create a logger to display information when running the script.
logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
logger = logging.getLogger('checkerboard_paradigm')


def build_checkerboard(dim):
    """Return ndarray of alternating ones and negative ones with shape
    (dim, dim)."""
    board = np.ones((dim, dim), dtype=np.int32)
    board[::2, ::2] = -1
    board[1::2, 1::2] = -1
    return board


# Set up LabStreamingLayer stream.
info = StreamInfo(name='checker_stream', type='Markers', channel_count=1,
                  channel_format='int32', source_id='checker_stream_001')
outlet = StreamOutlet(info)

# Create dictionary of markers. Keys are marker names. Values are lists of len
# `StreamInfo.channel_count` with the marker values.
markers = {
    'rest': [1],
    'checkerboard': [2],
    'test': [99],
}

logger.info("Sending triggers to test communication ...")
for _ in range(5):
   outlet.push_sample(markers['test'])
   core.wait(0.5)

# Default experiment arguments.
info = {
    'checkerboard size': 16,
    'flash frequency': 4,
    'number of trials': 10,
    'trial duration': 0.5,
    'inter-stimulus interval' : 0.,
}

# Show a dialog in which the user can change experiment arguments.
dlg = gui.DlgFromDict(dictionary=info, title="Checkerboard Paradigm")

# Quit if user does not press OK.
if not dlg.OK:
    core.quit()

dim = int(info['checkerboard size'])
period = 1. / float(info['flash frequency'])
n_trials = int(info['number of trials'])
trial_dur = float(info['trial duration'])
ISI_dur = float(info['inter-stimulus interval'])

# Raise ValueError if flashing period does not fit evenly into trial_dur.
if not (trial_dur / period).is_integer():
    raise ValueError("Division of trial duration ({}) by flashing period ({}) "
                     "has a non-zero remainder. This might cause unexpected "
                     "behavior.".format(trial_dur, period))

# Print the parameters being used.
param_msg = ("PARAMETERS\ndim: {}\nperiod: {}\nn_trials: {}\ntrial_dur: {}\n"
             "ISI_dur: {}".format(dim, period, n_trials, trial_dur, ISI_dur))
logger.debug(param_msg)

# Create boolean array to indicate whether to show checkerboard.
trials = [True, False] * (n_trials // 2)

# Instantiate the window.
win = visual.Window([800, 600], fullscr=True, allowGUI=False,
                    monitor='testMonitor', units='deg')

# Instantiate our stimuli.
instructions = visual.TextStim(win, pos=[0, 0], height=2.0,
                               text="Checkerboards will flash on the screen.")
board1 = build_checkerboard(dim)  # Create one checkerboard.
board2 = np.multiply(board1, -1)  # Multiply by -1 to create second board.
checkerboard1 = visual.GratingStim(tex=board1, win=win, interpolate=False,
                                   size=dim, sf=(0.5/dim))
checkerboard2 = visual.GratingStim(tex=board2, win=win, interpolate=False,
                                   size=dim, sf=(0.5/dim))
finished = visual.TextStim(win, pos=[0, 0], text="Finished!", height=2.0)

# Start the experiment.
instructions.draw()
win.flip()
core.wait(2.0)

# Loop through the trials.
for show_checkerboard in trials:
    if show_checkerboard:
        t0 = local_clock()
        outlet.push_sample(markers['checkerboard'])
        while local_clock() - t0 <= trial_dur:
            # Flash checkerboard. Flashing frequency is (1 / period).
            checkerboard1.draw()
            win.flip()
            core.wait(period)
            checkerboard2.draw()
            win.flip()
            core.wait(period)
            # Quit if a key is pressed.
            if event.getKeys():
                core.quit()
    else:
        t0 = local_clock()
        outlet.push_sample(markers['rest'])
        while local_clock() - t0 <= trial_dur:
            win.flip()  # Display nothing.
            # Quit if a key is pressed.
            if event.getKeys():
                core.quit()
    win.flip() # Clear the screen.
    core.wait(ISI_dur)

finished.draw()
win.flip()
core.wait(2.0)

win.close()
core.quit()
