"""Logging module for setting up app error logging."""
import logging
import sys


def setup_logger() -> logging.Logger:
    """Setting logger for the app"""
    logger = logging.getLogger('app')
    logger.setLevel(logging.ERROR)

    # StreamHandler за STDERR
    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setLevel(logging.ERROR)

    # Error Format
    stderr_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s')
    stderr_handler.setFormatter(stderr_formatter)

    logger.addHandler(stderr_handler)

    return logger
