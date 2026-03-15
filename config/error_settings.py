"""
error_settings.py
─────────────────
Central configuration for error handling behaviour across the app.
Import this wherever you need to check error handling policy.

All try/except blocks in views.py and services read their behaviour
from these settings — change here to affect everything.
"""

import os

# ─────────────────────────────────────────────────────────────
# General error behaviour
# ─────────────────────────────────────────────────────────────

# Show full Python traceback in HTTP responses (local only — never on production)
IS_RENDER       = os.environ.get("RENDER", "false").lower() == "true"
SHOW_TRACEBACKS = not IS_RENDER

# Include exception details in JSON API error responses
# False on production to avoid leaking internals
EXPOSE_API_ERRORS = not IS_RENDER

# ─────────────────────────────────────────────────────────────
# View-level error responses
# ─────────────────────────────────────────────────────────────

# Message shown to users when a page view fails
PAGE_ERROR_MESSAGE  = "Something went wrong. Please try again or contact the admin."

# Message shown in AJAX responses when an action fails
API_ERROR_MESSAGE   = "Action failed. Please try again."

# Redirect target when a POST action fails unexpectedly
ERROR_REDIRECT      = "/auction/"

# ─────────────────────────────────────────────────────────────
# Auction-specific guards
# ─────────────────────────────────────────────────────────────

# If True, any exception during sell/unsold/undo returns a safe error
# rather than crashing the auction session
SAFE_AUCTION_MODE   = True

# Maximum retries for DB operations before giving up
DB_RETRY_ATTEMPTS   = 3

# ─────────────────────────────────────────────────────────────
# Report / PDF errors
# ─────────────────────────────────────────────────────────────

# Return a plain-text error page instead of crash on PDF/Excel failure
REPORT_SAFE_MODE    = True

# ─────────────────────────────────────────────────────────────
# Helper: build a safe error message for API responses
# ─────────────────────────────────────────────────────────────

def api_error_response(exception, fallback=None):
    """
    Returns the message string to include in a JsonResponse error.
    On production: returns generic message. Locally: returns full exception text.
    """
    if EXPOSE_API_ERRORS:
        return str(exception)
    return fallback or API_ERROR_MESSAGE


def should_show_traceback():
    """True if we are in a local development environment."""
    return SHOW_TRACEBACKS
