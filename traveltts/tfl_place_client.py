# tfl_place_client.py

import logging
from typing import Any, Dict, List, Optional, Union

import requests

from config import TFL_APP_KEY, TFL_APP_ID  # define these placeholders in config.py

API_BASE = "https://api.tfl.gov.uk/Place/"


class TflPlaceClient:
    """
    Client for the TfL Unified API's /Place endpoint.
    You must set TFL_APP_ID and TFL_APP_KEY in config.py, e.g.:
        TFL_APP_ID = "tts"
        TFL_APP_KEY = "3a43c5de28f545a08b8e6b6aa3d9e4bc"
    """

    def __init__(self, app_id: str = TFL_APP_ID, app_key: str = TFL_APP_KEY) -> None:
        self.auth: Dict[str, str] = {"app_id": app_id, "app_key": app_key}

    def get_places_by_radius(
        self,
        lat: float,
        lon: float,
        radius: float = 1000,
        categories: Optional[List[str]] = None,
        include_children: bool = False,
        types: Optional[List[str]] = None,
        active_only: bool = False,
        max_results: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Fetch places within a circle of given radius (in metres) around (lat, lon).
        """
        params: Dict[str, Union[float, str, bool, int]] = {
            "Lat": lat,
            "Lon": lon,
            "radius": radius,
            "includeChildren": str(include_children).lower(),
            "activeOnly": str(active_only).lower(),
            **self.auth,
        }
        if categories:
            params["categories"] = ",".join(categories)
        if types:
            params["type"] = ",".join(types)
        if max_results is not None:
            params["numberOfPlacesToReturn"] = max_results

        try:
            resp = requests.get(API_BASE, params=params, timeout=10)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logging.error("TfL Place (radius) request failed: %s", e)
            return []

    def get_places_by_bbox(
        self,
        nw_lat: float,
        nw_lon: float,
        se_lat: float,
        se_lon: float,
        categories: Optional[List[str]] = None,
        include_children: bool = False,
        types: Optional[List[str]] = None,
        active_only: bool = False,
        max_results: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Fetch places within the bounding box defined by
        north-west (nw_lat, nw_lon) and south-east (se_lat, se_lon).
        Note: TfL does not document a bbox param name, so we use `bbox` here.
        """
        # TfL’s docs mention bounding‐box but don’t specify the exact param name.
        # In practice “bbox” = "northWestLat,northWestLon,southEastLat,southEastLon"
        bbox_val = f"{nw_lat},{nw_lon},{se_lat},{se_lon}"
        params: Dict[str, Union[str, bool, int]] = {
            "bbox": bbox_val,
            "includeChildren": str(include_children).lower(),
            "activeOnly": str(active_only).lower(),
            **self.auth,
        }
        if categories:
            params["categories"] = ",".join(categories)
        if types:
            params["type"] = ",".join(types)
        if max_results is not None:
            params["numberOfPlacesToReturn"] = max_results

        try:
            resp = requests.get(API_BASE, params=params, timeout=10)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logging.error("TfL Place (bbox) request failed: %s", e)
            return []
