"""PsychoPy experiment that shows a reversing checkerboard or nothing
in random order.

Open in PyschoPy Coder and press 'Run'.

ID          EVENT
-----------------
1   -->      open
2   -->    closed
99  -->      test
-----------------

"""
from __future__ import division

import random
import numpy as np
from pylsl import StreamInfo, StreamOutlet, local_clock

from psychopy import core, event, gui, prefs, visual
prefs.general['audioLib'] = ['pygame']
from psychopy import sound


# Setup LabStreamingLayer stream.
info = StreamInfo(name='eyes_stream', type='Markers', channel_count=1,
                  channel_format='int32', source_id='eyes_stream_001')
outlet = StreamOutlet(info)
markers = {
    'open': [1],
    'closed': [2],
    'test': [99],
}
# print("Sending triggers to test communication ...")
# for __ in range(5):
#    outlet.push_sample(markers['test'])
#    core.wait(0.5)


# Default experiment arguments.
info = {
    'number of trials': 4,
    'trial duration': 15.,
    'inter-stimulus interval' : 2.,
}

# Show a dialog in which the user can change experiment arguments.
dlg = gui.DlgFromDict(dictionary=info, title="Eyes Open/Closed Demonstration")

# Quit if user does not press OK.
if not dlg.OK: core.quit()

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
instructions_text = ("You will be instructed to open or close your eyes. If "
                    "instructed to close your eyes, open them once you hear a "
                    "sound.")
instructions = visual.TextStim(win, pos=[0, 0], text=instructions_text)
fixation = visual.TextStim(win, pos=[0, 0], text="+", height=2.0)

open_eyes_text = visual.TextStim(win, pos=[0, 0], text="Open", height=2.0)
close_eyes_text = visual.TextStim(win, pos=[0, 0], text="Closed", height=2.0)
end_of_close_eyes = sound.Sound('A', secs=0.5)

finished = visual.TextStim(win, pos=[0, 0], text="Finished!", height=2.0)


# Start the experiment!
instructions.draw()
win.flip()
core.wait(2.0)

for open_eyes in trials:
    if open_eyes:
        t0 = local_clock()
        print(markers['open'])  # outlet.push_sample(markers['open'])
        open_eyes_text.draw()
        win.flip()
        core.wait(trial_dur)
        if event.getKeys(): core.quit()  # Quit if a key was pressed.
    else:
        t0 = local_clock()
        print(markers['closed'])  # outlet.push_sample(markers['closed'])
        close_eyes_text.draw()
        win.flip()
        core.wait(trial_dur)
        if event.getKeys(): core.quit()  # Quit if a key was pressed.
    # Play sound after each type of stimulus to account for the effect of the
    # sound.
    end_of_close_eyes.play()

    win.flip() # Clear the screen.
    core.wait(ISI_dur)

finished.draw()
win.flip()
core.wait(2.0)

win.close()
core.quit()
