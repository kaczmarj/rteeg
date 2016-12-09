"""Real-time streaming and analysis of EEG data with feedback"""

# from .stream import (eeg_data, eeg_data_lock, incoming_triggers,
#                      incoming_triggers_lock, sfreq, channels, start_stream,
#                      get_thread, get_data)
# from .analyze import make_events

from .stream import Stream
from .analysis import LoopAnalysis
