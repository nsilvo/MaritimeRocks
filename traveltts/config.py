"""
Configuration for Greenwich Travel Report System.
"""

from typing import List, Tuple

# API keys (replace placeholders with real keys for production)
API_KEYS = {
    "WAZE": "TEST_WAZE_API_KEY_123",
    "INRIX": "TEST_INRIX_API_KEY_123",
    "TFL": "3a43c5de28f545a08b8e6b6aa3d9e4bc",
    
    # Google TTS uses GOOGLE_APPLICATION_CREDENTIALS env var instead
}

# Greenwich boundary polygon (lat, lon)
BOUNDARY_POLYGON: List[Tuple[float, float]] = [
    (51.5070, 0.0000),
    (51.4826, 0.0000),
    (51.4826, 0.0900),
    (51.5070, 0.0900),
]

# Roads to query for TfL Unified API
KEY_ROADS = ["A2", "A206", "A202", "Blackwall Tunnel Southern Approach"]

# Audio/report settings
AUDIO_FORMAT = "MP3"  # MP3 or LINEAR16
REPORT_LENGTH_MIN_SECONDS = 30
REPORT_LENGTH_MAX_SECONDS = 60
MAX_INCIDENTS_IN_REPORT = 5
TFL_APP_ID = "tts"
TFL_APP_KEY = "3a43c5de28f545a08b8e6b6aa3d9e4bc"
# Default Google TTS SSML settings
TTS_PROVIDER = "google"
GOOGLE_TTS = {
    "language_code": "en-GB",
    "voice_name": "en-GB-Wavenet-D",
    "speaking_rate": 1.0,
    "pitch": 0.0,
    "audio_encoding": AUDIO_FORMAT,
}

# External feeds
TFL_ROAD_DISRUPTION_ENDPOINT = "https://api.tfl.gov.uk/Road/all/Street/Disruption"
TFL_LIVE_TRAFFIC_URL = "https://api.tfl.gov.uk/Realtime/Disruptions/LiveTrafficDisruptions"
WEBTRIS_INCIDENTS_URL = "http://webtris.nationalhighways.co.uk/api/v1.0/incidents"
DFT_ANNUAL_TRAFFIC_URL = "https://roadtraffic.dft.gov.uk/api/AnnualAverageTraffic"
