"""
Sample data for simulating API responses.
"""

from typing import Any, Dict, List


def waze_sample_response() -> Dict[str, Any]:
    return {
        "incidents": [
            {
                "id": 1,
                "type": "ACCIDENT",
                "location": {"lat": 51.4940, "lon": 0.0480},
                "description": "Minor accident on A2 near Blackwall Tunnel",
                "severity": 2,
            },
            {
                "id": 2,
                "type": "JAM",
                "location": {"lat": 51.5000, "lon": 0.0200},
                "description": "Heavy congestion on A206 approaching Woolwich Road",
                "severity": 4,
            },
        ]
    }


def inrix_sample_response() -> Dict[str, Any]:
    return {
        "traffic_flow": [
            {
                "segment_id": "s1",
                "road": "A2",
                "location": {"lat": 51.4955, "lon": 0.0450},
                "speed_kmh": 15,
                "travel_time_s": 300,
            }
        ],
        "incidents": [
            {
                "id": "i1",
                "type": "ROAD_CLOSED",
                "location": {"lat": 51.5030, "lon": 0.0700},
                "description": "Road closed due to maintenance on Greenwich High Road",
                "impact": "high",
            }
        ],
    }


def local_roadworks() -> List[Dict[str, Any]]:
    return [
        {
            "id": "rw1",
            "type": "ROADWORK",
            "location": {"lat": 51.5060, "lon": 0.0300},
            "description": "Planned roadworks on Church Street until 18:00",
            "severity": 3,
        }
    ]
