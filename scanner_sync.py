"""
CasparCG Scanner Sync Script - PostgreSQL Version
Supports:
- Media table with 'type' (Music, GFX, Image)
- Category management (many-to-many linking)
- Standalone operation
"""

import argparse
import configparser
import json
import logging
import os
import signal
import sys
import time
import urllib.request
import psycopg2
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler
from typing import Dict

# Setup
stop_event = False
MEDIA_REFRESH_INTERVAL = 600

def setup_logger(name: str, filename: str) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    handler = TimedRotatingFileHandler(filename, when='midnight', backupCount=7)
    formatter = logging.Formatter('%(asctime)s %(levelname)s: %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger

logger = setup_logger("scanner_sync", "logs/scanner_sync.log")

def extract_artist_title(filename: str) -> (str, str):
    parts = filename.split('-')
    if len(parts) < 2:
        return ("Unknown Artist", filename.title())
    artist = parts[0].strip().title()
    title = ' '.join(parts[1:]).strip().title()
    return artist, title

def determine_type(file_path: str) -> str:
    ext = os.path.splitext(file_path)[1].lower()
    if ext in ['.mp4', '.mov', '.mkv']:
        return "Music"
    elif ext in ['.png', '.jpg', '.jpeg']:
        return "Image"
    else:
        return "Other"

def refresh_media(conn, scanner_url: str) -> None:
    try:
        with urllib.request.urlopen(scanner_url) as resp:
            media_list = json.load(resp)

        cur = conn.cursor()

        cur.execute("""
        CREATE TABLE IF NOT EXISTS media (
            id SERIAL PRIMARY KEY,
            path TEXT UNIQUE NOT NULL,
            type TEXT,
            size_bytes INTEGER,
            modified_ts TIMESTAMP,
            frames INTEGER,
            fps TEXT,
            duration DOUBLE PRECISION,
            last_seen TIMESTAMP,
            artist TEXT,
            title TEXT,
            release_year INTEGER,
            description TEXT,
            blocked INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS category (
            id SERIAL PRIMARY KEY,
            name TEXT UNIQUE NOT NULL
        );
        CREATE TABLE IF NOT EXISTS media_category (
            media_id INTEGER REFERENCES media(id) ON DELETE CASCADE,
            category_id INTEGER REFERENCES category(id) ON DELETE CASCADE,
            PRIMARY KEY (media_id, category_id)
        );
        """)
        conn.commit()

        scanned_paths = set()

        for item in media_list:
            if 'name' not in item or 'streams' not in item or not item['streams']:
                continue

            name = item['name']
            path = item['path'].replace('\\', '/').replace('media/', '')
            category_name = name.split('/')[0].strip().upper()
            file_type = determine_type(path)

            scanned_paths.add(name)

            video_stream = next((s for s in item['streams'] if s['codec']['type'] == 'video'), None)
            if not video_stream:
                continue

            fps = video_stream.get('time_base', '1/25')
            frames = int(video_stream.get('nb_frames', '0'))
            fps_num, fps_den = map(int, fps.split('/')) if '/' in fps else (1, 1)
            duration = frames / (fps_num / fps_den) if fps_den else 0

            ts = datetime.utcfromtimestamp(item['time'] / 1000)
            artist, title = extract_artist_title(name.split('/')[-1])

            # Insert media
            cur.execute("""
                INSERT INTO media (path, type, size_bytes, modified_ts, frames, fps, duration, last_seen,
                    artist, title, release_year, description)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NULL, NULL)
                ON CONFLICT (path) DO UPDATE SET
                    size_bytes = EXCLUDED.size_bytes,
                    modified_ts = EXCLUDED.modified_ts,
                    frames = EXCLUDED.frames,
                    fps = EXCLUDED.fps,
                    duration = EXCLUDED.duration,
                    last_seen = EXCLUDED.last_seen
            """, (name, file_type, item.get('size', 0), ts, frames, fps, duration, datetime.utcnow(), artist, title))

            # Get media ID
            cur.execute("SELECT id FROM media WHERE path = %s", (name,))
            media_id = cur.fetchone()[0]

            # Insert category
            cur.execute("INSERT INTO category (name) VALUES (%s) ON CONFLICT DO NOTHING", (category_name,))
            cur.execute("SELECT id FROM category WHERE name = %s", (category_name,))
            category_id = cur.fetchone()[0]

            # Insert mapping
            cur.execute("INSERT INTO media_category (media_id, category_id) VALUES (%s, %s) ON CONFLICT DO NOTHING", (media_id, category_id))

        conn.commit()
        logger.info("Media refresh completed.")

    except Exception as e:
        logger.error(f"Refresh failed: {e}")

# --- MAIN ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', default='config.ini', help='Path to config file')
    args = parser.parse_args()

    config = configparser.ConfigParser()
    config.read(args.config)

    scanner_url = config.get('scanner', 'url', fallback='http://localhost:8000/media')

    conn = psycopg2.connect(
        host=config.get('postgres', 'host'),
        port=config.getint('postgres', 'port'),
        dbname=config.get('postgres', 'dbname'),
        user=config.get('postgres', 'user'),
        password=config.get('postgres', 'password')
    )

    def shutdown(signum, frame):
        global stop_event
        stop_event = True
        logger.info("Shutdown requested.")

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    try:
        while not stop_event:
            refresh_media(conn, scanner_url)
            for _ in range(MEDIA_REFRESH_INTERVAL):
                if stop_event:
                    break
                time.sleep(1)
    except KeyboardInterrupt:
        shutdown(None, None)

    conn.close()
