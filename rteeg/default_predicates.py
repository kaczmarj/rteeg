"""Dictionary of default LabStreamingLayer predicates for different EEG
systems and for Markers streams.

The predicate string, e.g. "name='BioSemi'" or
"type='EEG' and starts-with(name,'BioSemi') and
count(description/desc/channels/channel)=32". For more info, refer to:
http://en.wikipedia.org/w/index.php?title=XPath_1.0&oldid=474981951.

Author: Jakub Kaczmarzyk, jakubk@mit.edu
"""
eeg = {
    'Enobio32': "type='EEG' and starts-with(desc/manufacturer,'NeuroElectrics')",
    'BioSemi32': "type='EEG'",
}

markers = {
    'default': "type='Markers'",
    'no_enobio': "type='Markers' and "
                 "not(starts-with(desc/manufacturer,'NeuroElectrics'))",
}
