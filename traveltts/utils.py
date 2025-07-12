"""
Utility functions.
"""

import datetime
from typing import Any, Dict, List, Tuple


def is_point_in_polygon(point: Tuple[float, float],
                        polygon: List[Tuple[float, float]]) -> bool:
    lat, lon = point
    num = len(polygon)
    j = num - 1
    inside = False
    for i in range(num):
        lat_i, lon_i = polygon[i]
        lat_j, lon_j = polygon[j]
        if ((lon_i > lon) != (lon_j > lon)) and \
           (lat < (lat_j - lat_i) * (lon - lon_i) / (lon_j - lon_i) + lat_i):
            inside = not inside
        j = i
    return inside


def safe_get(d: Dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        if isinstance(d, dict) and key in d:
            d = d[key]
        else:
            return default
    return d


def format_timestamp(dt: datetime.datetime = None) -> str:
    if dt is None:
        dt = datetime.datetime.utcnow()
    return dt.strftime("%Y%m%dT%H%M%SZ")


def clean_text(text: str) -> str:
    return " ".join(text.strip().split())
