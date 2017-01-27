# Real-Time EEG

[![Build Status](https://travis-ci.org/kaczmarj/rteeg.svg?branch=master)](https://travis-ci.org/kaczmarj/rteeg)

[![Coverage](https://codecov.io/gh/kaczmarj/rteeg/branch/master/graph/badge.svg)](https://codecov.io/gh/kaczmarj/rteeg/branch/master)


Python module to stream and analyze EEG data in real-time.


Dependencies
------------

- [LabStreamingLayer](https://github.com/sccn/labstreaminglayer) to stream EEG data and event triggers.
- [MNE-Python](https://github.com/mne-tools/mne-python) to analyze data.


How it works
------------

`rteeg` connects to a LabStreamingLayer (LSL) stream of raw EEG data or event markers and records the data being transmitted. The EEG data can then be analyzed in real-time in chunks with an analysis workflow provided by the user. The analysis workflow can be triggered whenever a buffer of a user-defined size becomes full, and visual feedback can be provided using HTML and CSS.


How to use it
-------------

To connect to a LabStreamingLayer (LSL) stream of EEG data, create an instance of the class `EEGStream`. The EEG system being used must be specified in the `eeg_system` argument. The program will search for a stream that matches the predicate [``default_predicates.eeg[`eeg_system`]``](rteeg/default_predicates.py). Predicates must be written in [XML Path Language](http://en.wikipedia.org/w/index.php?title=XPath_1.0&oldid=474981951) and can be added or removed to suit the user's needs.

Once connected to an EEG stream, data can be converted to `mne.Raw` or `mne.Epochs` objects with methods `make_raw()` and `make_epochs()`, respectively. A stream of event markers is required to make an `mne.Epochs` object. Connect to a LSL stream of event markers by creating an instance of the class `MarkerStream`.


Independent Component Analysis
------------------------------

It is also possible to use Independent Component Analysis (ICA) to remove artifacts each time data is retrieved. The ICA solution must first be computed (a.k.a. "fit") on some data, and components must be selected for removal. Use the method `EEGStream.fit_ica()` to fit the ICA. This returns an `mne.preprocessing.ICA` object, which is stored in `EEGStream.ica`. Plot the sources of the ICA using `EEGStream.viz_ica()`, and select the components that should be removed. If the ICA object has been fit and components have been selected for removal, these components will be removed from incoming data when using `EEGStream.make_raw()`.


Looping analysis
----------------

A function can be called each time a buffer of EEG data increases by a user-defined amount.



Saving data
-----------

To save the data at the end of the recording session, use `make_raw().save(fname)`, where `fname` is the filename. This saves the EEG data as a `FIF` file. If an instance of `MarkerStream` is supplied, events should be present in the EEG data.


How to use it if you don't have an EEG cap
------------------------------------------

Included in this repo is a [script that transmits synthetic EEG data](demonstrations/synthesize_data/send_eeg_data.py) over a LabStreamingLayer stream. Simply run that file (`python send_eeg_data.py` in a terminal) in order to try `rteeg`. Event markers can be sent by running the file `send_markers.py` in the same directory.


How to save fitted models
-------------------------

Fitted machine learning models should be included in a dictionary that also includes important information about that model. The information included in the dictionary is very important because the number of features in the training set must be equal to the number of features in the testing set. Seemingly minor differences between the processing steps of training and testing sets could result in unequal numbers of features. The dictionary can look like this:

```python
clf_dictionary = {
    'paradigm' : "In inattention condition, subjects looked at a crosshair. "
                 "In attention, subjects played sudoku.",
    'processing': "Data were FIR filtered (0.5 to 40 Hz), and "
                  "artifacts were removed with ICA. Power "
                  "spectral density was computed (0.5 to 7.0 Hz), and PCA "
                  "(15 components) was computed on the power. The output "
                  "of PCA served as the features for the model.",
    'n_samples_for_training' : 65,
    'n_features': 15,
    'classifier' : ExtraTreesClassifier(),  # Fitted model here.
}
```

The dictionary should be saved to a JSON file. Pickling the dictionary is discouraged because of the instability and security risks of pickle files.
