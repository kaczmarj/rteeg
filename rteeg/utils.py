"""Package-wide utilities."""
# Author: Jakub Kaczmarzyk <jakubk@mit.edu>
import logging


# MNE wants EEG values in volts.
SCALINGS = {
    # Scale of incoming data: factory by which to multiply to get volts.
    'volts': 1.,
    'millivolts': 1. / 1e+3,
    'microvolts': 1. / 1e+6,
    'nanovolts': 1. / 1e+9,
    'unknown': 1.,
}


def _create_logger():
    # Create logger.
    logger = logging.getLogger('rteeg')
    logger.setLevel(logging.DEBUG)
    # Create console handler.
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    # Create formatter and add to ch.
    formatter = logging.Formatter('%(message)s')
    ch.setFormatter(formatter)
    # Add ch to logger.
    logger.addHandler(ch)
    return logger


logger = _create_logger()


def set_log_level(verbosity):
    logger.setLevel(verbosity)
