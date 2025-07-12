"""
Database models for the Greenwich Travel Report system.
"""

import json
from datetime import datetime
from typing import Any, List, Tuple

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class BoundingPolygon(db.Model):
    __tablename__ = "bounding_polygons"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True, nullable=False)
    coords_json = db.Column(db.Text, nullable=False)

    def get_coords(self) -> List[Tuple[float, float]]:
        return json.loads(self.coords_json)

    def set_coords(self, coords: Any) -> None:
        self.coords_json = json.dumps(coords)


class CustomLine(db.Model):
    __tablename__ = "custom_lines"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), unique=True, nullable=False)
    script = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=True)

    def is_active(self) -> bool:
        """
        Returns True if this line has not expired.
        """
        if self.expires_at is None:
            return True
        return self.expires_at > datetime.utcnow()

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "script": self.script,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
        }


class Incident(db.Model):
    __tablename__ = "incidents"
    id = db.Column(db.String(64), primary_key=True)
    source = db.Column(db.String(32), nullable=False, index=True)
    type = db.Column(db.String(64))
    lat = db.Column(db.Float)
    lon = db.Column(db.Float)
    description = db.Column(db.Text)
    severity = db.Column(db.Integer)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class AudioReport(db.Model):
    __tablename__ = "audio_reports"
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(256), nullable=False)
    script = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class TTSSettings(db.Model):
    __tablename__ = "tts_settings"
    id = db.Column(db.Integer, primary_key=True)
    engine = db.Column(db.String(32), nullable=False)
    settings_json = db.Column(db.Text, nullable=False)

    def get_settings(self) -> Any:
        return json.loads(self.settings_json)

    def set_settings(self, s: Any) -> None:
        self.settings_json = json.dumps(s)
