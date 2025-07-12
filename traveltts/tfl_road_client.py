import logging
from typing import Any, Dict, List

import requests

API_BASE = "https://api.tfl.gov.uk/Road/"


class TflRoadClient:
    """
    Simple client for TfL’s /Road endpoints (no app key needed).
    """

    def get_corridors(self) -> List[Dict[str, Any]]:
        """
        GET https://api.tfl.gov.uk/Road/
        Returns list of RoadCorridor objects.
        """
        try:
            resp = requests.get(API_BASE, timeout=10)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logging.error("Failed to fetch road corridors: %s", e)
            return []

    def get_disruptions(self, corridor_id: str) -> List[Dict[str, Any]]:
        """
        GET https://api.tfl.gov.uk/Road/{corridorId}/Disruption
        Returns list of disruptions for that corridor.
        """
        url = f"{API_BASE}{corridor_id}/Disruption"
        try:
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logging.error("Failed to fetch disruptions for %s: %s", corridor_id, e)
            return []
