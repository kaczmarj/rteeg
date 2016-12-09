# Real-Time EEG

Python module to stream and analyze EEG data in real-time.


Dependencies
------------
- [LabStreamingLayer](https://github.com/sccn/labstreaminglayer) to stream EEG data and event triggers.
- [MNE-Python](https://github.com/mne-tools/mne-python) to analyze data.


How it works
------------
`rteeg` connects to a LabStreamingLayer stream of raw EEG data or event markers and records the data being transmitted. The data can then be analyzed in real-time in chunks with an analysis workflow provided by the user. The analysis workflow can be triggered whenever a buffer of a user-defined size becomes full.


How to use it
-------------
Refer to the Jupyter Notebook `sample.ipynb` for a use example. Here is a minimal use example:

  ```python
  In [1]: %matplotlib qt

  In [2]: import rteeg

  In [3]: rt = rteeg.Stream()

  In [4]: rt.connect(eeg=True, markers=True, eeg_montage='Enobio32')
  Searching for EEG stream ...
  Searching for Markers stream ...

  In [5]:
  Connected to Markers stream. Connected to EEG stream.

  In [5]: print rt.recording_duration()
  80.15

  In [6]: rt.fit_ica(10)  # Fit ICA on next 10 seconds of data.
  [........................................] 100.00000 | Collecting data
  Computing ICA solution ...
  Finished in 0.82 s
  Out[6]: <ICA  |  raw data decomposition, fit (extended-infomax): 1000
  samples, 32 components, channels used: "eeg">

  In [7]: rt.ica.plot_sources(rt.raw_for_ica)
  Out[7]: <matplotlib.figure.Figure at 0x11c1a5150>

  In [8]: print(rt.ica.exclude)  # Components marked for exclusion.
  [1, 2]

  In [9]: rt.ica.apply(rt.raw_for_ica).plot(scalings='auto')
  Out[9]: <matplotlib.figure.Figure at 0x103c9fe90>

  In [10]: rt.make_raw(20)  # Applies ICA automatically.
  Out[10]: <RawArray  |  None, n_channels x n_times : 33 x 2000 (20.0 sec),
  ~588 kB, data loaded>

  In [11]: # One can make a function that performs the necessary analyses.
  # This function can be called every time a buffer of EEG data reaches a
  # user-defined size.
  ```

First, initialize the class `Stream()`. Then, call the `connect()` method and specify which type(s) of stream(s) the script should look for (either `"EEG"` or `"Markers"`). At any point in time, EEG data from the previous X seconds can be retrieved using the method `make_raw(X)`. If event markers are being streamed in addition to the EEG data, the previous X seconds of data can be epoched automatically according to the event markers with the method `make_epochs(X)`.

It is also possible to use Independent Component Analysis (ICA) to remove artifacts each time data is retrieved. The ICA solution must first be computed on some data (i.e., "fit"), and the "bad" components must be selected for removal. Use the method `fit_ica(X)` to fit the ICA. This returns an `mne.preprocessing.ICA` object. Plot the sources of the ICA and select the components that should be removed. This ICA can be applied to all incoming data using the `apply()` method of the `ICA` object.

To save the data at the end of the recording session, use `make_raw().save(fname)`, where `fname` is the filename. This saves the EEG data as a `FIF` file.


Classification
--------------
Support will be added for classification with machine learning. A function will be included that triggers the user's analysis workflow every time a buffer of EEG data reaches a user-defined size. Support will also be added to train a model during an experiment.


How to use it if you don't have an EEG cap
------------------------------------------
The only thing preventing you from using `rteeg` is a LabStreamingLayer stream of EEG data. Included in this repo is a script that transmits synthetic EEG data over a LabStreamingLayer stream (`demonstrations/synthesize_data/send_eeg_data.py`). Simply run that file (`python send_eeg_data.py` in a terminal), and then you can try (or debug) `rteeg`.


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
