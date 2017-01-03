"""Real-time streaming and analysis of EEG data with feedback"""
from .analysis import LoopAnalysis
from .base import resolve_streams
from .stream import EEGStream, MarkerStream
