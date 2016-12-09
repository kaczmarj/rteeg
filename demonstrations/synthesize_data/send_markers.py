"""Example program to demonstrate how to send markers into LSL."""

import random
import time

from pylsl import StreamInfo, StreamOutlet

info = StreamInfo(name='markers', type='Markers', channel_count=1,
                  channel_format='int32', source_id='markers_test1234')

# next make an outlet
outlet = StreamOutlet(info)

print("now sending markers...")
while True:
    # pick a sample to send an wait for a bit
    trigger = random.choice([1, 2])
    outlet.push_sample([trigger])
    print(trigger)
    time.sleep(5.0)
