from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
from pydantic import BaseModel
from sqlalchemy import create_engine, MetaData, Table, Column, Integer, String, Float, select, func, text
from sqlalchemy.orm import sessionmaker
import requests
import time
import re
import os

# Database setup
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_URL = f"sqlite:///{os.path.join(BASE_DIR, '..', 'db', 'media_cache.db')}"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)
metadata = MetaData()

# Tables
media = Table(
    "media", metadata,
    Column("id", Integer, primary_key=True),
    Column("path", String),
    Column("artist", String),
    Column("title", String),
    Column("release_year", Integer),
    Column("description", String),
    Column("type", String),
    Column("blocked", Integer),
    Column("duration", Float),
    Column("category", String)
)
playlog = Table(
    "playlog", metadata,
    Column("id", Integer, primary_key=True),
    Column("media_id", Integer),
    Column("started", String)
)

# FastAPI app
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
    category: Optional[str] = None

class MediaUpdate(BaseModel):
    artist: Optional[str] = None
    title: Optional[str] = None
    release_year: Optional[int] = None
    description: Optional[str] = None
    blocked: Optional[int] = None
    category: Optional[str] = None

class DashboardStats(BaseModel):
    total_clips: int
    blocked_clips: int
    clips_per_category: dict
    recent_played_clips: list

# API routes


def clean_string(text):
    if not text:
        return text
    text = re.sub(r'\(.*?\)', '', text)  # Remove (content)
    text = re.sub(r'[^a-zA-Z0-9\s]', '', text)  # Remove special chars
    text = re.sub(r'\s+', ' ', text)  # Collapse spaces
    return text.strip()

@app.post("/autofill_release_years")
def autofill_release_years():
    with engine.begin() as conn:
        result = conn.execute(
            select(media.c.id, media.c.artist, media.c.title)
            .where((media.c.release_year.is_(None)) | (media.c.release_year == 0))
        )
        tracks = [dict(row._mapping) for row in result]

        print(f"Found {len(tracks)} tracks missing release_year.")

        updated = 0
        for track in tracks:
            artist = clean_string(track.get("artist"))
            title = clean_string(track.get("title"))

            if not artist or not title:
                continue

            query = f'artist:"{artist}" recording:"{title}"'
            url = f"https://musicbrainz.org/ws/2/recording/?query={query}&fmt=json"
            print(f"Searching MusicBrainz: {url}")

            tries = 0
            while tries < 2:  # Max 2 tries
                try:
                    response = requests.get(
                        url,
                        headers={"User-Agent": "MaritimeRocksBot/1.0 (your@email.com)"},
                        timeout=10
                    )

                    # Always throttle - 1 request per second
                    time.sleep(1)

                    if response.status_code == 503:
                        print(f"MusicBrainz 503 encountered. Throttling... waiting 5 seconds before retry.")
                        time.sleep(5)
                        tries += 1
                        continue  # Retry once
                    elif response.status_code == 200:
                        data = response.json()
                        if data.get("recordings"):
                            first_recording = data["recordings"][0]
                            release_date = first_recording.get("first-release-date")
                            if release_date:
                                year = int(release_date[:4])
                                print(f"Found year {year} for {artist} - {title}")
                                update_stmt = media.update().where(media.c.id == track["id"]).values(release_year=year)
                                conn.execute(update_stmt)
                                updated += 1
                            else:
                                print(f"No release date found for {artist} - {title}")
                        else:
                            print(f"No recordings found for {artist} - {title}")
                    else:
                        print(f"MusicBrainz API error {response.status_code} for {artist} - {title}")
                    break  # Exit retry loop
                except Exception as e:
                    print(f"Error processing {artist} - {title}: {e}")
                    break

    return {"updated_entries": updated}

@app.get("/media", response_model=List[Media])
def list_media(category: Optional[str] = None):
    stmt = select(media)
    if category:
        stmt = stmt.where(media.c.category == category)
    with engine.connect() as conn:
        result = conn.execute(stmt)
        return [dict(row._mapping) for row in result]

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
        category_counts = conn.execute(select(media.c.category, func.count()).group_by(media.c.category)).fetchall()
        recent_played = conn.execute(
            text("""
            SELECT playlog.id, media.artist, media.title, playlog.started
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
