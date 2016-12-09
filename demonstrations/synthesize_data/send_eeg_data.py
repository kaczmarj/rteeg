"""Example program to demonstrate how to send a multi-channel time series to
LSL."""

import random
import time

import numpy as np

from pylsl import StreamInfo, StreamOutlet

# Our desired frequency.
sfreq = 1 / 100.
ch_names = [
    'Fp1','Fp2','AF3','AF4','F3','F4','F7','F8','FC5','FC6','T7','T8',
    'FC1','FC2','C3','C4','CP5','CP6','P7','P8','CP1','CP2','P3','P4','O1','O2',
    'PO3','PO4','Oz','Pz','Cz','Fz']
n_chs = len(ch_names)

info = StreamInfo('EEG_stream', 'EEG', len(ch_names), 100, 'float32',
                  'uniqueID1234567890')

# Manufacturer is not actually NeuroElectrics. We include this so that
# rteeg.stream can identify and connect to this LabStreamingLayer stream.
info.desc().append_child_value("manufacturer", "NeuroElectrics")
info.desc().append_child_value("nominal_srate", "100")
for c in ch_names:
    info.desc().append_child("channel")\
        .append_child_value("name", c)\
        .append_child_value("unit", "microvolts")\
        .append_child_value("type", "EEG")

outlet = StreamOutlet(info)

print("now sending EEG data...")

Fs = 8000
f = 50
i = 1
while True:
    y = np.sin(2 * np.pi * f * i / Fs)
    sample = [y for __ in xrange(n_chs)]
    noise = np.random.normal(0, 1, n_chs)
    sample = sample + noise
    outlet.push_sample(sample)
    i += 1
    time.sleep(sfreq)
