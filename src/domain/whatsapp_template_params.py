"""Helpers for sanitizing strings that will travel to a WhatsApp template body.

WhatsApp Cloud API rejects template body parameters that contain newline/tab
characters or runs of more than 4 consecutive spaces (Meta error 132018:
"Param text cannot have new-line/tab characters or more than 4 consecutive
spaces"). The sanitizer is applied both at write time (so the UI shows the
text exactly as it will be sent) and at send time (defensive net for
historical data already in storage).
"""

import re


def sanitize_template_param(value: str) -> str:
    """Make a string safe to send as a WhatsApp template body parameter.

    Replace newline/tab characters with a visible separator and cap runs of
    consecutive spaces below Meta's 5-space limit. The output is always
    stripped of surrounding whitespace.
    """
    no_breaks = re.sub(r"[\n\t\r]+", " · ", value)
    collapsed = re.sub(r" {4,}", "   ", no_breaks)
    return collapsed.strip()
