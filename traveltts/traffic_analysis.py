"""
Merge, dedupe, and prioritize incidents.
"""

from dataclasses import dataclass
from typing import List, Dict, Any


@dataclass
class IncidentData:
    id: str
    source: str
    type: str
    lat: float
    lon: float
    description: str
    severity: int


class TrafficFusion:
    @staticmethod
    def merge(incidents: List[Dict[str, Any]]) -> List[IncidentData]:
        fused: Dict[str, IncidentData] = {}
        for inc in incidents:
            key = f"{inc['type']}_{round(inc['lat'],3)}_{round(inc['lon'],3)}"
            obj = IncidentData(**inc)  # type: ignore
            if key in fused:
                if obj.severity > fused[key].severity:
                    fused[key] = obj
            else:
                fused[key] = obj
        return list(fused.values())


class Analyzer:
    @staticmethod
    def prioritize(incidents: List[IncidentData],
                   max_items: int) -> List[IncidentData]:
        return sorted(incidents, key=lambda i: i.severity, reverse=True)[:max_items]
