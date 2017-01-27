"""Package-wide utilities."""
# Author: Jakub Kaczmarzyk <jakubk@mit.edu>
import logging


def create_logger():
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


def set_log_level(verbosity):
    logger.setLevel(verbosity)


logger = create_logger()
