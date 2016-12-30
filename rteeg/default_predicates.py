"""Dictionary of default LabStreamingLayer predicates for different EEG
systems.

These predicates can be changed to meet the user's requirements.


The predicate string, e.g. "name='BioSemi'" or
"type='EEG' and starts-with(name,'BioSemi') and
count(description/desc/channels/channel)=32". For more info, refer to:
http://en.wikipedia.org/w/index.php?title=XPath_1.0&oldid=474981951.


Last updated 12/30/2016.

Author: Jakub Kaczmarzyk, jakubk@mit.edu
"""

default_predicates = {
    'Enobio32': "type='EEG' and starts-with(desc/manufacturer,'NeuroElectrics')",
    'BioSemi32': "type='EEG'",
}
