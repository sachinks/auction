"""
log_settings.py
───────────────
Central configuration for all logging behaviour.
Import this in logging_config.py — change settings here only.

Environment overrides (set as env vars):
  LOG_LEVEL        — override default log level (DEBUG / INFO / WARNING / ERROR)
  LOG_MAX_BYTES    — max size per log file before rotation (default 1 MB)
  LOG_BACKUP_COUNT — how many rotated files to keep (default 5)
"""

import os

# ─────────────────────────────────────────────────────────────
# Log directory
# ─────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_DIR  = os.environ.get("LOG_DIR", os.path.join(BASE_DIR, "logs"))

# ─────────────────────────────────────────────────────────────
# Log levels
# ─────────────────────────────────────────────────────────────
import logging

_level_map = {
    "DEBUG":   logging.DEBUG,
    "INFO":    logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR":   logging.ERROR,
}

DEFAULT_LOG_LEVEL  = _level_map.get(os.environ.get("LOG_LEVEL", "INFO").upper(), logging.INFO)
ERROR_LOG_LEVEL    = logging.ERROR      # error.log only captures ERROR and above
SYSTEM_LOG_LEVEL   = logging.INFO       # system.log captures INFO and above
AUCTION_LOG_LEVEL  = logging.INFO       # auction.log captures INFO and above

# ─────────────────────────────────────────────────────────────
# Rotation settings
# ─────────────────────────────────────────────────────────────
LOG_MAX_BYTES    = int(os.environ.get("LOG_MAX_BYTES",    1_000_000))   # 1 MB per file
LOG_BACKUP_COUNT = int(os.environ.get("LOG_BACKUP_COUNT", 5))           # keep 5 rotated files

# ─────────────────────────────────────────────────────────────
# Log file names
# ─────────────────────────────────────────────────────────────
LOG_FILES = {
    "auction": "auction.log",   # bid actions, results, match outcomes
    "error":   "error.log",     # all exceptions with tracebacks
    "system":  "system.log",    # admin actions, imports, pool/fixture management
    "access":  "access.log",    # HTTP request log (optional, via middleware)
}

# ─────────────────────────────────────────────────────────────
# Format strings
# ─────────────────────────────────────────────────────────────
LOG_FORMAT         = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
LOG_DATE_FORMAT    = "%Y-%m-%d %H:%M:%S"
ERROR_FORMAT       = "%(asctime)s | %(levelname)-8s | %(name)s | %(funcName)s:%(lineno)d | %(message)s"

# ─────────────────────────────────────────────────────────────
# Console output
# Set to True locally for live debugging, False on Render
# ─────────────────────────────────────────────────────────────
IS_RENDER         = os.environ.get("RENDER", "false").lower() == "true"
CONSOLE_ENABLED   = not IS_RENDER        # local: print to terminal; Render: file only
CONSOLE_LOG_LEVEL = logging.DEBUG        # console shows DEBUG and above locally
