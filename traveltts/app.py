"""
app.py

Flask web UI for Greenwich Travel Report:
  - OSM map with editable bounding polygon & incident markers
  - Custom lines CRUD with expiration
  - Ingestion endpoint to pull all feeds
  - “Generate Report” pipeline including custom lines
  - Audio reports list with playback
  - TTS settings editor with dropdowns & sliders
  - Voice listing and on-the-fly HD WaveNet samples
  - TfL “Place” listing by radius
  - TfL Road corridors and disruption details
"""

import os
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
)
from flask_sqlalchemy import SQLAlchemy
from google.cloud import texttospeech

from config import (
    BOUNDARY_POLYGON,
    TTS_PROVIDER,
    GOOGLE_TTS,
    MAX_INCIDENTS_IN_REPORT,
)
from models import (
    db,
    BoundingPolygon,
    CustomLine,
    Incident,
    AudioReport,
    TTSSettings,
)
from data_ingestion import ingest_all
from traffic_analysis import TrafficFusion, Analyzer
from report_generator import ReportGenerator
from tts_client import TTSClient
from tfl_place_client import TflPlaceClient
from tfl_road_client import TflRoadClient


def create_app() -> Flask:
    """Create and configure the Flask application."""
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///traffic.db"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SECRET_KEY"] = "change-this-in-production"
    db.init_app(app)
    return app


app = create_app()


def init_db() -> None:
    """
    Initialize database tables and seed defaults:
      - default 'greenwich' polygon
      - default TTS settings
    """
    db.create_all()

    if not BoundingPolygon.query.filter_by(name="greenwich").first():
        bp = BoundingPolygon(name="greenwich")
        bp.set_coords(BOUNDARY_POLYGON)
        db.session.add(bp)

    if not TTSSettings.query.first():
        ts = TTSSettings(
            engine=TTS_PROVIDER,
            settings_json=json.dumps(GOOGLE_TTS),
        )
        db.session.add(ts)

    db.session.commit()


with app.app_context():
    init_db()
    os.makedirs(os.path.join(app.root_path, "static", "reports"), exist_ok=True)
    os.makedirs(os.path.join(app.root_path, "static", "samples"), exist_ok=True)


@app.route("/")
def index() -> Any:
    """Home: map with polygon, incidents, and custom lines."""
    bp = BoundingPolygon.query.filter_by(name="greenwich").first()
    polygon: List[Tuple[float, float]] = bp.get_coords() if bp else []

    incs = Incident.query.order_by(Incident.timestamp.desc()).all()
    incidents = [
        {"id": inc.id, "lat": inc.lat, "lon": inc.lon, "description": inc.description}
        for inc in incs
        if inc.lat is not None and inc.lon is not None
    ]

    lines = CustomLine.query.order_by(CustomLine.name).all()

    return render_template(
        "index.html",
        polygon=polygon,
        incidents=incidents,
        lines=lines,
    )


@app.route("/polygon", methods=["GET", "POST"])
def edit_polygon() -> Any:
    """Edit Greenwich bounding polygon via Leaflet Draw."""
    bp = BoundingPolygon.query.filter_by(name="greenwich").first()
    error: Optional[str] = None

    if request.method == "POST":
        raw = request.form.get("coords", "")
        try:
            coords = json.loads(raw)
            if not isinstance(coords, list):
                raise ValueError("Must be a JSON list of [lat, lon] pairs")
            bp.set_coords(coords)
            db.session.commit()
            flash("Bounding polygon updated.", "success")
            return redirect(url_for("index"))
        except Exception as e:
            error = f"Invalid JSON: {e}"

    return render_template(
        "polygon.html",
        coords_json=bp.coords_json if bp else "[]",
        error=error,
    )


@app.route("/lines", methods=["GET", "POST"])
def manage_lines() -> Any:
    """Add/list custom lines (with script & optional expiry)."""
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        script = request.form.get("script", "").strip()
        exp_raw = request.form.get("expires_at", "").strip()
        expires_at: Optional[datetime] = None
        if exp_raw:
            try:
                expires_at = datetime.fromisoformat(exp_raw)
            except ValueError:
                flash("Invalid expiry format.", "danger")
                return redirect(url_for("manage_lines"))

        if not name or not script:
            flash("Both name and script are required.", "danger")
        elif CustomLine.query.filter_by(name=name).first():
            flash(f"Line '{name}' already exists.", "warning")
        else:
            cl = CustomLine(name=name, script=script, expires_at=expires_at)
            db.session.add(cl)
            db.session.commit()
            flash(f"Added custom line '{name}'.", "success")
        return redirect(url_for("manage_lines"))

    now = datetime.utcnow()
    lines = (
        CustomLine.query
        .filter(
            (CustomLine.expires_at == None) | (CustomLine.expires_at > now)
        )
        .order_by(CustomLine.created_at.desc())
        .all()
    )
    return render_template("lines.html", lines=lines)


@app.route("/lines/delete/<int:line_id>", methods=["POST"])
def delete_line(line_id: int) -> Any:
    """Delete a custom line."""
    cl = CustomLine.query.get_or_404(line_id)
    db.session.delete(cl)
    db.session.commit()
    flash(f"Deleted custom line '{cl.name}'.", "info")
    return redirect(url_for("manage_lines"))


@app.route("/incidents")
@app.route("/incidents/<source>")
def view_incidents(source: Optional[str] = None) -> Any:
    """View stored incidents, optionally filtered by source."""
    query = Incident.query
    if source:
        query = query.filter_by(source=source.upper())
    incs = query.order_by(Incident.timestamp.desc()).all()
    return render_template("incidents.html", incidents=incs, source=source)


@app.route("/refresh")
def refresh_incidents() -> Any:
    """Ingest all feeds, upsert into DB, then redirect to incidents."""
    bp = BoundingPolygon.query.filter_by(name="greenwich").first()
    boundary = bp.get_coords() if bp else BOUNDARY_POLYGON

    raw = ingest_all(boundary)
    new_count = 0
    for inc in raw:
        existing = Incident.query.get(inc["id"])
        if existing:
            existing.type = inc.get("type")
            existing.lat = inc.get("lat")
            existing.lon = inc.get("lon")
            existing.description = inc.get("description")
            existing.severity = inc.get("severity")
        else:
            db.session.add(Incident(
                id=inc["id"],
                source=inc.get("source"),
                type=inc.get("type"),
                lat=inc.get("lat"),
                lon=inc.get("lon"),
                description=inc.get("description"),
                severity=inc.get("severity"),
            ))
            new_count += 1
    db.session.commit()
    flash(f"Ingested {len(raw)} incidents ({new_count} new).", "info")
    return redirect(url_for("view_incidents"))


@app.route("/generate")
def generate_report() -> Any:
    """Full pipeline: ingest, analyze, generate, synthesize, save & list reports."""
    ts = TTSSettings.query.first()
    cfg: Dict[str, Any] = json.loads(ts.settings_json)

    audio_enc = (
        texttospeech.AudioEncoding.MP3
        if cfg["audio_encoding"] == "MP3"
        else texttospeech.AudioEncoding.LINEAR16
    )
    tts = TTSClient(
        language_code=cfg["language_code"],
        voice_name=cfg["voice_name"],
        speaking_rate=cfg["speaking_rate"],
        pitch=cfg["pitch"],
        audio_encoding=audio_enc,
    )

    bp = BoundingPolygon.query.filter_by(name="greenwich").first()
    boundary = bp.get_coords() if bp else BOUNDARY_POLYGON
    raw = ingest_all(boundary)
    fused = TrafficFusion.merge(raw)
    prio = Analyzer.prioritize(fused, MAX_INCIDENTS_IN_REPORT)

    now = datetime.utcnow()
    custom_lines = (
        CustomLine.query
        .filter(
            (CustomLine.expires_at == None) | (CustomLine.expires_at > now)
        )
        .order_by(CustomLine.created_at.desc())
        .all()
    )
    custom_scripts = [cl.script for cl in custom_lines]

    script = ReportGenerator().generate_script(prio, custom_scripts)
    out_dir = os.path.join(app.root_path, "static", "reports")
    path = tts.synthesize(script, out_dir)
    fname = os.path.basename(path)

    db.session.add(AudioReport(filename=fname, script=script))
    db.session.commit()

    flash(f"Generated audio report: {fname}", "success")
    return redirect(url_for("list_reports"))


@app.route("/reports")
def list_reports() -> Any:
    """List generated audio reports."""
    reports = AudioReport.query.order_by(AudioReport.created_at.desc()).all()
    return render_template("reports.html", reports=reports)


@app.route("/settings", methods=["GET", "POST"])
def tts_settings() -> Any:
    """View/edit TTS settings via dropdowns & sliders."""
    ts = TTSSettings.query.first()
    error: Optional[str] = None

    if request.method == "POST":
        data = {
            "language_code": request.form["language_code"],
            "voice_name": request.form["voice_name"],
            "speaking_rate": float(request.form["speaking_rate"]),
            "pitch": float(request.form["pitch"]),
            "audio_encoding": request.form["audio_encoding"],
        }
        try:
            for key in (
                "language_code",
                "voice_name",
                "speaking_rate",
                "pitch",
                "audio_encoding",
            ):
                if key not in data:
                    raise KeyError(f"Missing {key}")
            ts.settings_json = json.dumps(data)
            db.session.commit()
            flash("TTS settings updated.", "success")
            return redirect(url_for("tts_settings"))
        except Exception as e:
            error = str(e)

    settings_dict = json.loads(ts.settings_json)
    return render_template(
        "settings.html",
        settings=settings_dict,
        error=error,
    )


@app.route("/voices")
def list_voices() -> Any:
    """List available HD WaveNet voices for current language."""
    ts = TTSSettings.query.first()
    settings = json.loads(ts.settings_json)

    client = TTSClient(
        language_code=settings["language_code"],
        voice_name=settings["voice_name"],
        speaking_rate=settings["speaking_rate"],
        pitch=settings["pitch"],
        audio_encoding=texttospeech.AudioEncoding.MP3,
    )
    voices = client.list_voices(language_code=settings["language_code"])

    return render_template("voices.html", voices=voices, settings=settings)


@app.route("/sample/<voice_name>")
def voice_sample(voice_name: str) -> Any:
    """Generate (if needed) and serve a short sample for the given voice."""
    sample_dir = os.path.join(app.root_path, "static", "samples")
    filename = f"{voice_name}.mp3"
    filepath = os.path.join(sample_dir, filename)

    if not os.path.exists(filepath):
        ts = TTSSettings.query.first()
        cfg = json.loads(ts.settings_json)
        tts = TTSClient(
            language_code=cfg["language_code"],
            voice_name=voice_name,
            speaking_rate=cfg["speaking_rate"],
            pitch=cfg["pitch"],
            audio_encoding=texttospeech.AudioEncoding.MP3,
        )
        tts.synthesize(
            f"This is a sample of the voice {voice_name}.",
            output_dir=sample_dir,
            filename=filename,
        )

    return redirect(url_for("static", filename=f"samples/{filename}"))


@app.route("/places")
def list_places() -> Any:
    """List TfL “Places” within 1 km of Greenwich Park."""
    client = TflPlaceClient()
    places = client.get_places_by_radius(
        lat=51.4769,
        lon=0.0005,
        radius=1000,
        types=["BikePoint"],
        active_only=True,
        max_results=50,
    )
    return render_template("places.html", places=places)


@app.route("/roads")
def list_roads() -> Any:
    """Show all TfL road corridors with their status."""
    client = TflRoadClient()
    corridors = client.get_corridors()
    return render_template("roads.html", corridors=corridors)


@app.route("/roads/<corridor_id>")
def road_detail(corridor_id: str) -> Any:
    """Show map + disruptions for a single corridor."""
    client = TflRoadClient()
    disruptions = client.get_disruptions(corridor_id)
    meta = {c["id"]: c for c in client.get_corridors()}
    corridor = meta.get(corridor_id.lower())
    if corridor and "envelope" in corridor:
        try:
            corridor["envelope"] = json.loads(corridor["envelope"])
        except Exception:
            corridor["envelope"] = []
    return render_template(
        "road_detail.html",
        corridor=corridor,
        disruptions=disruptions,
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    app.run(debug=True)
