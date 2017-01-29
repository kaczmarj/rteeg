"""PsychoPy experiment that shows a reversing checkerboard or nothing
in random order.

Open in PyschoPy Coder and press 'Run'.

ID             EVENT
--------------------
1   -->      control
2   --> checkerboard
99  -->         test
--------------------

In ISI, include support for tuple, in which case random value between both
values is selected to be ISI.

Parameters
----------
checkerboard size : int (defaults to 8)
    Size of checkerboard. If 8, will show 8x8 checkerboard.
flash frequency : int, float (defaults to 4)
    Frequency with which the checkerboard should flash in Hz. If 4, will switch
    between checkerboard and its inverse four times per second.
number of trials : int (defaults to 10)
    Total number of trials. Should be even so that the number of control
    and checkerboard trials are equal, but does not have to be even.
trial duration : int, float (defaults to 1.)
    Duration of each trial in seconds.
inter-stimulus interval : int, float (defaults to .5)
    Duration of inter-stimulus interval in seconds.
"""
from __future__ import division, print_function

import random
import numpy as np
from pylsl import StreamInfo, StreamOutlet, local_clock

from psychopy import core, event, gui, visual


def build_checkerboard(dim):
    """Return two 2D ndarrays of shape (dim, dim). Both arrays have
    alternating ones and negative ones, but the order is switched between the
    arrays."""
    board = np.ones((dim, dim), dtype=np.int32)
    board[::2, ::2] = -1
    board[1::2, 1::2] = -1
    return board, np.multiply(board, -1)

# Setup LabStreamingLayer stream.
info = StreamInfo(name='checkerboard_stream', type='Markers', channel_count=1,
                  channel_format='int32', source_id='checkerboard_stream_001')
outlet = StreamOutlet(info)
markers = {
    'control': [1],
    'checkerboard': [2],
    'test': [99],
}

print("Sending triggers to test communication ...")
for _ in range(5):
   outlet.push_sample(markers['test'])
   core.wait(0.5)

# Default experiment arguments.
info = {
    'checkerboard size': 8,
    'flash frequency': 4,
    'number of trials': 10,
    'trial duration': 2.,
    'inter-stimulus interval' : .5,
}

# Show a dialog in which the user can change experiment arguments.
dlg = gui.DlgFromDict(dictionary=info, title="Checkerboard Demonstration")

# Quit if user does not press OK.
if not dlg.OK:
    core.quit()

dim = info['checkerboard size']
srate = 1 / info['flash frequency']
n_trials = info['number of trials']
trial_dur = info['trial duration']
ISI_dur = info['inter-stimulus interval']


# Create a boolean array to indicate whether to show checkerboard.
trials = [i for i in range(n_trials // 2) for i in [True, False]]
np.random.shuffle(trials)  # Shuffles list in-place.


# Instantiate the window.
win = visual.Window([800, 600], allowGUI=False, monitor='testMonitor',
                    units='deg')

# Instantiate our stimuli.
instructions = visual.TextStim(win, pos=[0, 0],
                               text="Images will flash on the screen.")
fixation = visual.TextStim(win, pos=[0, 0], text="+", height=2.0)
board1, board2 = build_checkerboard(dim)
checkerboard1 = visual.GratingStim(tex=board1, win=win, interpolate=False,
                                   size=dim, sf=(1 / dim))
checkerboard2 = visual.GratingStim(tex=board2, win=win, interpolate=False,
                                   size=dim, sf=(1 / dim))
control_board = visual.GratingStim(tex=np.zeros((dim, dim)), win=win,
                                   interpolate=False, size=dim, sf=(1/dim))
finished = visual.TextStim(win, pos=[0, 0], text="Finished!", height=2.0)

# Start the experiment!
instructions.draw()
win.flip()
core.wait(2.0)

# Loop through the trials.
for show_checkerboard in trials:
    if show_checkerboard:
        t0 = local_clock()
        print(markers['checkerboard'])  # outlet.push_sample(markers['checkerboard'])
        while local_clock() - t0 <= trial_dur:
            checkerboard1.draw()
            win.flip()
            core.wait(srate)
            checkerboard2.draw()
            win.flip()
            core.wait(srate)
            if event.getKeys(): core.quit()  # Quit if a key was pressed.
    else:
        t0 = local_clock()
        print(markers['control'])  # outlet.push_sample(markers['control'])
        while local_clock() - t0 <= trial_dur:
            control_board.draw()
            win.flip()
            if event.getKeys(): core.quit()

    win.flip() # Clear the screen.
    core.wait(ISI_dur)

finished.draw()
win.flip()
core.wait(2.0)

win.close()
core.quit()
