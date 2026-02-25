import os
import gzip
import shutil
import logging
from logging.handlers import TimedRotatingFileHandler

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_DIR = os.path.join(BASE_DIR, "logs")
os.makedirs(LOG_DIR, exist_ok=True)


class CompressedTimedRotatingFileHandler(TimedRotatingFileHandler):
    def doRollover(self):
        super().doRollover()

        # Compress the latest rotated file
        for filename in os.listdir(LOG_DIR):
            if filename.startswith(self.baseFilename.split(os.sep)[-1]) and not filename.endswith(".gz"):
                full_path = os.path.join(LOG_DIR, filename)

                if os.path.isfile(full_path):
                    with open(full_path, "rb") as f_in:
                        with gzip.open(full_path + ".gz", "wb") as f_out:
                            shutil.copyfileobj(f_in, f_out)
                    os.remove(full_path)


LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,

    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {name} {message}",
            "style": "{",
        },
        "simple": {
            "format": "{levelname} {message}",
            "style": "{",
        },
    },

    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "simple",
        },

        "file_all": {
            "level": "DEBUG",
            "class": "config.logging_config.CompressedTimedRotatingFileHandler",
            "filename": os.path.join(LOG_DIR, "app.log"),
            "when": "midnight",
            "backupCount": 7,
            "formatter": "verbose",
        },

        "file_info": {
            "level": "INFO",
            "class": "config.logging_config.CompressedTimedRotatingFileHandler",
            "filename": os.path.join(LOG_DIR, "info.log"),
            "when": "midnight",
            "backupCount": 7,
            "formatter": "verbose",
        },

        "file_error": {
            "level": "ERROR",
            "class": "config.logging_config.CompressedTimedRotatingFileHandler",
            "filename": os.path.join(LOG_DIR, "error.log"),
            "when": "midnight",
            "backupCount": 14,
            "formatter": "verbose",
        },
    },

    "loggers": {
        "": {
            "handlers": ["console", "file_all", "file_info", "file_error"],
            "level": "DEBUG",
            "propagate": True,
        },

        "django": {
            "handlers": ["file_all", "file_error"],
            "level": "INFO",
            "propagate": False,
        },

        "cricket": {
            "handlers": ["file_all", "file_info", "file_error"],
            "level": "DEBUG",
            "propagate": False,
        },
    },
}