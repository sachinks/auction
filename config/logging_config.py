import logging
from logging.handlers import RotatingFileHandler
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

LOG_DIR = os.path.join(BASE_DIR, "logs")

if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)


def get_logger(name, filename):

    logger = logging.getLogger(name)

    if logger.handlers:
        return logger

    handler = RotatingFileHandler(
        os.path.join(LOG_DIR, filename),
        maxBytes=1_000_000,
        backupCount=5
    )

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(message)s"
    )

    handler.setFormatter(formatter)

    logger.addHandler(handler)

    logger.setLevel(logging.INFO)

    return logger


auction_logger = get_logger("auction", "auction.log")
error_logger = get_logger("error", "error.log")
system_logger = get_logger("system", "system.log")