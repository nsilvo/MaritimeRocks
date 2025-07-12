"""
Fetch and parse traffic data from multiple sources.
"""

import logging
import xml.etree.ElementTree as ET
from typing import Any, Dict, List

import requests

from config import (
    API_KEYS, BOUNDARY_POLYGON, KEY_ROADS,
    TFL_ROAD_DISRUPTION_ENDPOINT, TFL_LIVE_TRAFFIC_URL,
    WEBTRIS_INCIDENTS_URL, DFT_ANNUAL_TRAFFIC_URL
)
from test_data import (
    waze_sample_response, inrix_sample_response,
    local_roadworks
)
from utils import safe_get, is_point_in_polygon


class WazeClient:
    def __init__(self, api_key: str = API_KEYS["WAZE"]) -> None:
        self.api_key = api_key

    def fetch(self) -> Dict[str, Any]:
        try:
            return waze_sample_response()
        except Exception as e:
            logging.warning("Waze fetch failed: %s", e)
            return {}

    def parse(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        out = []
        for inc in data.get("incidents", []):
            out.append({
                "id": f"W{inc['id']}",
                "source": "WAZE",
                "type": inc["type"],
                "lat": safe_get(inc, "location", "lat"),
                "lon": safe_get(inc, "location", "lon"),
                "description": inc.get("description", ""),
                "severity": inc.get("severity", 1),
            })
        return out


class INRIXClient:
    def __init__(self, api_key: str = API_KEYS["INRIX"]) -> None:
        self.api_key = api_key

    def fetch(self) -> Dict[str, Any]:
        try:
            return inrix_sample_response()
        except Exception as e:
            logging.warning("INRIX fetch failed: %s", e)
            return {}

    def parse(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        severity_map = {"low": 1, "medium": 2, "high": 3}
        out = []
        for inc in data.get("incidents", []):
            out.append({
                "id": f"I{inc['id']}",
                "source": "INRIX",
                "type": inc["type"],
                "lat": safe_get(inc, "location", "lat"),
                "lon": safe_get(inc, "location", "lon"),
                "description": inc.get("description", ""),
                "severity": severity_map.get(inc.get("impact","low"),1),
            })
        return out


class LocalRoadworksSource:
    @staticmethod
    def load() -> List[Dict[str, Any]]:
        return local_roadworks()


class TFLRoadDisruptionClient:
    def __init__(self, api_key: str = API_KEYS["TFL"]) -> None:
        self.api_key = api_key

    def fetch(self, road_id: str) -> Any:
        url = TFL_ROAD_DISRUPTION_ENDPOINT.format(road_id=road_id)
        try:
            resp = requests.get(url, params={"app_key": self.api_key})
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logging.warning("TfL fetch failed for %s: %s", road_id, e)
            return []

    def parse(self, data: Any) -> List[Dict[str, Any]]:
        out = []
        for d in data:
            coords = d.get("geometry",{}).get("coordinates", [])
            if len(coords)>=2:
                lon, lat = coords
                out.append({
                    "id": f"TFLR{d.get('disruptionId','')}",
                    "source": "TFL_ROAD",
                    "type": d.get("disruptionCategory",""),
                    "lat": lat,
                    "lon": lon,
                    "description": d.get("description",""),
                    "severity": {"Low":1,"Medium":2,"High":3}.get(d.get("severity","Low"),1),
                })
        return out


class TFLLiveTrafficClient:
    def fetch(self) -> str:
        try:
            r = requests.get(TFL_LIVE_TRAFFIC_URL)
            r.raise_for_status()
            return r.text
        except Exception as e:
            logging.warning("TfL live XML fetch failed: %s", e)
            return ""

    def parse(self, xml_text: str) -> List[Dict[str, Any]]:
        out = []
        if not xml_text:
            return out
        try:
            root = ET.fromstring(xml_text)
            for item in root.findall(".//Incident"):
                lat = float(item.findtext("Latitude","0"))
                lon = float(item.findtext("Longitude","0"))
                desc = item.findtext("Description","").strip()
                sev = int(item.findtext("Severity","1"))
                out.append({
                    "id": f"TFLL{item.findtext('ID','')}",
                    "source": "TFL_LIVE",
                    "type": item.findtext("Type",""),
                    "lat": lat, "lon": lon,
                    "description": desc,
                    "severity": sev,
                })
        except Exception as e:
            logging.warning("XML parse error: %s", e)
        return out


class WebTRISClient:
    def fetch(self) -> Dict[str, Any]:
        try:
            r = requests.get(WEBTRIS_INCIDENTS_URL)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            logging.warning("WebTRIS fetch failed: %s", e)
            return {}

    def parse(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        out = []
        for inc in data.get("incidents", []):
            out.append({
                "id": f"WTR{inc.get('id','')}",
                "source": "WEBTRIS",
                "type": inc.get("type",""),
                "lat": safe_get(inc,"lat"),
                "lon": safe_get(inc,"lon"),
                "description": inc.get("description",""),
                "severity": inc.get("severity",1),
            })
        return out


class DFTTrafficStatsClient:
    def fetch(self) -> List[Dict[str, Any]]:
        try:
            r = requests.get(DFT_ANNUAL_TRAFFIC_URL)
            r.raise_for_status()
            return r.json().get("AnnualAverageTraffic",[])
        except Exception as e:
            logging.warning("DfT stats fetch failed: %s", e)
            return []


def normalize_and_filter(incidents: List[Dict[str, Any]],
                         boundary: List[Any]) -> List[Dict[str, Any]]:
    return [
        inc for inc in incidents
        if inc.get("lat") is not None
        and inc.get("lon") is not None
        and is_point_in_polygon((inc["lat"],inc["lon"]), boundary)
    ]


def ingest_all(boundary: List[Any]) -> List[Dict[str, Any]]:
    all_incidents = []
    all_incidents += WazeClient().parse(WazeClient().fetch())
    all_incidents += INRIXClient().parse(INRIXClient().fetch())
    all_incidents += LocalRoadworksSource.load()

    tfl_rd = TFLRoadDisruptionClient()
    for road in KEY_ROADS:
        all_incidents += tfl_rd.parse(tfl_rd.fetch(road))

    tfl_live = TFLLiveTrafficClient()
    all_incidents += tfl_live.parse(tfl_live.fetch())

    all_incidents += WebTRISClient().parse(WebTRISClient().fetch())

    stats = DFTTrafficStatsClient().fetch()
    logging.info("DfT stats records: %d", len(stats))

    return normalize_and_filter(all_incidents, boundary)
