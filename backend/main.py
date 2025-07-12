# Updated FastAPI backend with PostgreSQL + multi-category support + playback logging

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
from pydantic import BaseModel
from sqlalchemy import create_engine, MetaData, Table, Column, Integer, String, Float, select, func, text, insert, delete, and_, desc
from sqlalchemy import update
from sqlalchemy.orm import sessionmaker
import requests
import time
import re
import os
import configparser
from datetime import datetime, timedelta

# Load PostgreSQL config
config = configparser.ConfigParser()
config.read(os.path.join(os.path.dirname(__file__), "config.ini"))
pg = config["postgres"]

DATABASE_URL = (
    f"postgresql+psycopg2://{pg['user']}:{pg['password']}@{pg['host']}:{pg['port']}/{pg['dbname']}"
)

engine = create_engine(DATABASE_URL, isolation_level="AUTOCOMMIT")
SessionLocal = sessionmaker(bind=engine)
metadata = MetaData()

# Tables
media = Table(
    "media", metadata,
    Column("id", Integer, primary_key=True),
    Column("path", String, nullable=False),
    Column("type", String),
    Column("size_bytes", Integer),
    Column("modified_ts", String),
    Column("frames", Integer),
    Column("fps", String),
    Column("duration", Float),
    Column("last_seen", String),
    Column("artist", String),
    Column("title", String),
    Column("release_year", Integer),
    Column("description", String),
    Column("blocked", Integer, default=0),
)

category = Table(
    "category", metadata,
    Column("id", Integer, primary_key=True),
    Column("name", String, nullable=False, unique=True)
)

media_category = Table(
    "media_category", metadata,
    Column("media_id", Integer, nullable=False),
    Column("category_id", Integer, nullable=False)
)

playlog = Table(
    "playlog", metadata,
    Column("id", Integer, primary_key=True),
    Column("media_id", Integer),
    Column("started", String),
    Column("duration", Float)
)

# FastAPI app setup
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Models
class Media(BaseModel):
    id: int
    path: str
    artist: Optional[str]
    title: Optional[str]
    release_year: Optional[int]
    description: Optional[str]
    type: Optional[str]
    blocked: Optional[int]
    duration: Optional[float]

class MediaUpdate(BaseModel):
    artist: Optional[str] = None
    title: Optional[str] = None
    release_year: Optional[int] = None
    description: Optional[str] = None
    blocked: Optional[int] = None

class DashboardStats(BaseModel):
    total_clips: int
    blocked_clips: int
    clips_per_category: dict
    recent_played_clips: list

class CategoryCreate(BaseModel):
    name: str

class CategoryList(BaseModel):
    id: int
    name: str

class MediaCategoryAssign(BaseModel):
    category_names: List[str]

class PlaybackLogEntry(BaseModel):
    media_id: int
    timestamp: Optional[str] = None
    duration: Optional[float] = None

# Category Endpoints
@app.get("/categories", response_model=List[CategoryList])
def list_categories():
    with engine.connect() as conn:
        result = conn.execute(select(category)).fetchall()
        return [dict(row._mapping) for row in result]

@app.post("/categories", response_model=CategoryList)
def create_category(cat: CategoryCreate):
    with engine.begin() as conn:
        existing = conn.execute(select(category).where(category.c.name == cat.name)).fetchone()
        if existing:
            return dict(existing._mapping)
        result = conn.execute(insert(category).values(name=cat.name).returning(category))
        return dict(result.fetchone()._mapping)

@app.get("/media/{media_id}/categories", response_model=List[str])
def get_categories_for_media(media_id: int):
    with engine.connect() as conn:
        result = conn.execute(
            select(category.c.name)
            .select_from(media_category.join(category))
            .where(media_category.c.media_id == media_id)
        ).fetchall()
        return [row[0] for row in result]

@app.post("/media/{media_id}/categories")
def assign_categories(media_id: int, payload: MediaCategoryAssign):
    with engine.begin() as conn:
        cat_map = {}
        for name in payload.category_names:
            result = conn.execute(select(category).where(category.c.name == name)).fetchone()
            if result:
                cat_map[name] = result[0]
            else:
                inserted = conn.execute(insert(category).values(name=name).returning(category)).fetchone()
                cat_map[name] = inserted[0]

        conn.execute(delete(media_category).where(media_category.c.media_id == media_id))

        for cat_id in cat_map.values():
            conn.execute(insert(media_category).values(media_id=media_id, category_id=cat_id))
    return {"message": "Categories updated"}

# Playback Logging Endpoint
@app.post("/log_play")
def log_playback(entry: PlaybackLogEntry):
    ts = entry.timestamp or datetime.utcnow().isoformat()
    stmt = insert(playlog).values(media_id=entry.media_id, started=ts, duration=entry.duration)
    with engine.begin() as conn:
        conn.execute(stmt)
    return {"message": "Playback logged"}

# Helper for release year

def clean_string(text):
    if not text:
        return text
    text = re.sub(r'\(.*?\)', '', text)
    text = re.sub(r'[^a-zA-Z0-9\s]', '', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

@app.post("/autofill_release_years")
def autofill_release_years():
    updated = 0
    with engine.connect() as conn:
        result = conn.execute(
            select(media.c.id, media.c.artist, media.c.title)
            .where((media.c.release_year.is_(None)) | (media.c.release_year == 0))
            .where(media.c.blocked == 0)
        )
        tracks = [dict(row._mapping) for row in result]

    for track in tracks:
        artist = re.sub(r"\(.*?\)", "", (track.get("artist") or "")).strip()
        title = re.sub(r"\(.*?\)", "", (track.get("title") or "")).strip()
        if not artist or not title:
            continue

        query = f'artist:"{artist}" recording:"{title}"'
        url = f"https://musicbrainz.org/ws/2/recording/?query={query}&fmt=json"

        try:
            response = requests.get(
                url,
                headers={"User-Agent": "MaritimeRocksBot/1.0 (you@example.com)"},
                timeout=10
            )
            time.sleep(1)  # 1 request per second throttle
            if response.status_code == 200:
                data = response.json()
                recordings = data.get("recordings", [])
                if recordings:
                    release_date = recordings[0].get("first-release-date")
                    if release_date:
                        try:
                            year = int(release_date[:4])
                            with engine.begin() as conn:
                                stmt = update(media).where(media.c.id == track["id"]).values(release_year=year)
                                conn.execute(stmt)
                            updated += 1
                        except Exception as e:
                            print(f"Failed to update {track['id']}: {e}")
        except Exception as e:
            print(f"Request error for {artist} - {title}: {e}")

    return {"updated_entries": updated}

# Media search and list
@app.get("/media", response_model=List[dict])
def search_media(q: str = "", category_filter: str = None):
    with engine.connect() as conn:
        stmt = select(media)
        if q:
            stmt = stmt.where(
                media.c.artist.ilike(f"%{q}%") | media.c.title.ilike(f"%{q}%")
            )
        result = conn.execute(stmt).fetchall()
        all_rows = [dict(row._mapping) for row in result]

        if category_filter:
            category_ids = conn.execute(
                select(category.c.id).where(category.c.name == category_filter)
            ).fetchall()
            if category_ids:
                allowed_ids = set(
                    r[0] for r in conn.execute(
                        select(media_category.c.media_id)
                        .where(media_category.c.category_id == category_ids[0][0])
                    ).fetchall()
                )
                all_rows = [row for row in all_rows if row["id"] in allowed_ids]
        return all_rows

@app.patch("/media/{media_id}")
def update_media(media_id: int, data: MediaUpdate):
    stmt = media.update().where(media.c.id == media_id).values(**data.dict(exclude_unset=True))
    with engine.begin() as conn:
        conn.execute(stmt)
    return {"message": "Media updated successfully"}

@app.delete("/media/{media_id}")
def delete_media(media_id: int):
    stmt = media.delete().where(media.c.id == media_id)
    with engine.begin() as conn:
        conn.execute(stmt)
    return {"message": "Media deleted successfully"}

@app.get("/dashboard", response_model=DashboardStats)
def get_dashboard():
    with engine.connect() as conn:
        total = conn.execute(select(func.count()).select_from(media)).scalar()
        blocked = conn.execute(select(func.count()).select_from(media).where(media.c.blocked == 1)).scalar()
        category_counts = conn.execute(
            text("""
            SELECT c.name, COUNT(mc.media_id)
            FROM category c
            LEFT JOIN media_category mc ON mc.category_id = c.id
            GROUP BY c.name
            """)
        ).fetchall()

        recent_played = conn.execute(
            text("""
            SELECT playlog.id, media.artist, media.title, media.duration, media.fps, media.frames, playlog.started, playlog.duration
            FROM playlog
            LEFT JOIN media ON playlog.media_id = media.id
            ORDER BY playlog.started DESC
            LIMIT 10
            """)
        ).fetchall()

        return {
            "total_clips": total,
            "blocked_clips": blocked,
            "clips_per_category": {row[0] or "Uncategorized": row[1] for row in category_counts},
            "recent_played_clips": [dict(row._mapping) for row in recent_played]
        }
class NextClip(BaseModel):
    id: int
    path: str
    artist: Optional[str]
    title: Optional[str]
    release_year: Optional[int]
    duration: Optional[float]

# Endpoint: /next_clip
@app.get("/next_clip", response_model=NextClip)
def get_next_clip():
    recent_cutoff = datetime.utcnow() - timedelta(hours=1)
    with engine.connect() as conn:
        subquery = (
            select(playlog.c.media_id, func.max(playlog.c.started).label("last_played"))
            .group_by(playlog.c.media_id)
        ).subquery()

        stmt = (
            select(media)
            .outerjoin(subquery, media.c.id == subquery.c.media_id)
            .where(media.c.blocked == 0)
            .where(media.c.type == 'Music')
            .where(
                (subquery.c.last_played.is_(None)) |
                (subquery.c.last_played < recent_cutoff.isoformat())
            )
            .order_by(func.random())
            .limit(1)
        )

        result = conn.execute(stmt).fetchone()
        if not result:
            raise HTTPException(status_code=404, detail="No eligible clip found")

        row = dict(result._mapping)
        if row.get("artist"):
            row["artist"] = re.sub(r"[\[(](.*?)[\])]", "", row["artist"]).strip().title()
        if row.get("title"):
            row["title"] = re.sub(r"[\[(](.*?)[\])]", "", row["title"]).strip().title()
        return NextClip(**row)