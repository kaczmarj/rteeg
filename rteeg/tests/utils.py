from threading import Thread, Event
import time
import numpy as np
from pylsl import local_clock, StreamInfo, StreamOutlet

class SyntheticData(object):
    """Synthesize data for testing purposes."""
    def __init__(self, type_, n_chs, sfreq, send_data=False):
        """Add docstring here."""
        if type_ not in ["Markers", "EEG"]:
            raise ValueError("`type_` must be 'Markers' or 'EEG'.")
        self.type_ = type_
        self.n_chs = n_chs
        self.sfreq = sfreq
        self.send_data = send_data

        self.stream_name = "test_{}".format(self.type_)
        self.stream_type = 'float32' if self.type_ == "EEG" else 'int32'

        info = StreamInfo(self.stream_name, self.type_, self.n_chs, self.sfreq,
                          self.stream_type, self.stream_name + '_1234')
        # Add metadata.
        info.desc().append_child_value("nominal_srate", str(self.sfreq))
        if self.type_ == "EEG":
            ch_names = ['ch{}'.format(x) for x in range(1, self.n_chs + 1)]
            for c in ch_names:
                info.desc().append_child("channel")\
                    .append_child_value("name", c)\
                    .append_child_value("unit", "millivolts")\
                    .append_child_value("type", "EEG")
        self.outlet = StreamOutlet(info)
        if self.send_data:
            self.event = Event()
            self.thread = Thread(target=self._send_data)
            self.thread.start()

    def _send_data(self):
        sample = [1] * self.n_chs
        while not self.event.is_set():
            self.outlet.push_sample(sample)
            time.sleep(1 / self.sfreq)

    def create_data(self, n_samples):
        data = []
        start_time = 422826.210533354  # This is arbitrary.
        this_time = start_time
        for _ in range(n_samples):
            data.append([1] * self.n_chs + [this_time])
            this_time += 1. / self.sfreq
        return data

    def stop(self):
        if self.send_data:
            self.event.set()
            self.thread.join()
        del self.outlet


# This is the array of events that results from merging EEG and Marker data.
true_markers = np.array([[  0,   0,   1],
                         [ 79,   0,   1],
                         [179,   0,   1],
                         [279,   0,   1],
                         [379,   0,   1],
                         [479,   0,   1],
                         [579,   0,   1],
                         [679,   0,   1],
                         [779,   0,   1],
                         [879,   0,   1]], dtype=np.int32)
