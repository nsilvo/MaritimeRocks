"""
Generates textual travel report scripts.
"""

import logging
from typing import List, Optional

from config import (
    REPORT_LENGTH_MIN_SECONDS,
    REPORT_LENGTH_MAX_SECONDS,
    MAX_INCIDENTS_IN_REPORT,
)
from traffic_analysis import IncidentData
from utils import clean_text


class ReportGenerator:
    """
    Creates a natural-language travel report script, 30–60s long,
    including any custom lines at the end.
    """

    SPEECH_RATE_WPM = 150  # words per minute

    def __init__(
        self,
        min_secs: int = REPORT_LENGTH_MIN_SECONDS,
        max_secs: int = REPORT_LENGTH_MAX_SECONDS,
        max_incidents: int = MAX_INCIDENTS_IN_REPORT,
    ) -> None:
        self.min_secs = min_secs
        self.max_secs = max_secs
        self.max_incidents = max_incidents

    def estimate_duration(self, script: str) -> float:
        """
        Estimate speech duration in seconds.
        """
        words = len(script.split())
        return words / (self.SPEECH_RATE_WPM / 60)

    def generate_script(
        self,
        incidents: List[IncidentData],
        custom_lines_scripts: Optional[List[str]] = None
    ) -> str:
        """
        Build a 30–60s travel report:
        - Reports each incident description.
        - Appends each custom-line script entry.
        """
        intro = "Good morning, this is your Greenwich travel update."
        outro = "That's all for now. Stay safe on the roads."
        body: List[str] = []

        # Top incidents
        for inc in incidents[: self.max_incidents]:
            body.append(inc.description)

        # Custom lines
        if custom_lines_scripts:
            for script in custom_lines_scripts:
                body.append(script)

        # Combine
        script = " ".join([intro] + body + [outro])
        script = clean_text(script)

        # Trim if too long
        duration = self.estimate_duration(script)
        if duration > self.max_secs:
            allowed = max(1, int(self.max_incidents * self.max_secs / duration))
            trimmed = body[:allowed]
            # always include custom lines at end
            custom_part = body[self.max_incidents :]
            script = clean_text(" ".join([intro] + trimmed + custom_part + [outro]))

        logging.debug("Final script (~%.1f sec): %s", self.estimate_duration(script), script)
        return script
