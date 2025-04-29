#!/usr/bin/env python3
"""
CasparCG Rock-Music Automation System
Auto refreshes media, plays random clips, metadata-driven, manual keyboard control.
"""

import argparse
import configparser
import json
import logging
import os
import platform
import random
import re
import signal
import socket
import sqlite3
import sys
import termios
import threading
import time
import tty
import xml.etree.ElementTree as ET
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler
from typing import Any, Dict, Optional, Tuple

# Global control
IS_WINDOWS = platform.system() == "Windows"

if not IS_WINDOWS:
    import termios
    import tty

stop_event = threading.Event()
CONSOLE_ACTIVE = sys.stdin.isatty()

MEDIA_REFRESH_INTERVAL = 600  # seconds
ANTI_REPEAT_SECONDS = 1 * 3600  # 3 hours
ARTIST_REPEAT_SECONDS = 0.2 * 3600  # 1 hour

# Setup thread-specific loggers
def setup_logger(name: str, filename: Optional[str] = None) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    if filename:
        file_handler = TimedRotatingFileHandler(filename, when='midnight', backupCount=7)
        file_formatter = logging.Formatter('%(asctime)s %(levelname)s: %(message)s')
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

    if name == "console_monitor" and CONSOLE_ACTIVE:
        console_handler = logging.StreamHandler(sys.stdout)
        console_formatter = logging.Formatter('[%(asctime)s] %(message)s')
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)

    logger.propagate = False
    return logger


monitor_logger = setup_logger("monitor", "logs/monitor.log")
playback_logger = setup_logger("playback", "logs/playback.log")
refresher_logger = setup_logger("refresher", "logs/refresher.log")
console_logger = setup_logger("console_monitor", "")

# CasparCG Client
class CasparCGClient:
    def __init__(self, host: str, port: int) -> None:
        self.host = host
        self.port = port
        self.sock: Optional[socket.socket] = None
        self.lock = threading.Lock()
        self.connect()

    def connect(self) -> None:
        while not stop_event.is_set():
            try:
                self.sock = socket.create_connection((self.host, self.port))
                self.sock.settimeout(5)
                logging.info(f"\rConnected to CasparCG server at {self.host}:{self.port}")
                break
            except Exception as e:
                logging.error(f"\rConnection failed: {e}, retrying...")
                time.sleep(5)

    def send(self, command: str) -> None:
        with self.lock:
            if not self.sock:
                self.connect()
            try:
                self.sock.sendall((command + '\r\n').encode('utf-8'))
                logging.debug(f"\rSent command: {command}")
            except Exception:
                self.connect()
                self.sock.sendall((command + '\r\n').encode('utf-8'))

    def receive(self) -> str:
        with self.lock:
            buffer = ''
            while not stop_event.is_set():
                try:
                    data = self.sock.recv(4096)
                    if not data:
                        raise Exception("Disconnected")
                    buffer += data.decode('utf-8')
                    if '\r\n\r\n' in buffer:
                        break
                except Exception:
                    if stop_event.is_set():
                        break
                    self.connect()
                    return self.receive()
            return buffer.strip()
    
    def receive_info(self) -> str:
        with self.lock:
            buffer = ''
            while not stop_event.is_set():
                try:
                    data = self.sock.recv(4096)
                    if not data:
                        raise Exception("Disconnected")
                    buffer += data.decode('utf-8')
                    if '</channel>' in buffer:
                        break
                except Exception:
                    if stop_event.is_set():
                        break
                    self.connect()
                    return self.receive()
            return buffer.strip()

    def send_receive(self, command: str) -> str:
        self.send(command)
        return self.receive()
    
    def send_receive_info(self, command: str) -> str:
        self.send(command)
        return self.receive_info()

# Parse helper functions
def parse_cls_line(line: str) -> Optional[Dict[str, Any]]:
    match = re.match(r'^"(?P<path>[^"]+)"\s+(?P<type>STILL|MOVIE)\s+(?P<size>\d+)\s+(?P<timestamp>\d{14})\s+(?P<frames>\d+)\s+(?P<fps>\d+/\d+)$', line)
    if match:
        g = match.groupdict()
        num, den = map(int, g['fps'].split('/'))
        fps = num / den if den else 0
        if fps == 0:
            refresher_logger.debug(f"\rSkipping invalid FPS line: {line}")
            return None
        duration = int(g['frames']) / fps
        ts = datetime.strptime(g['timestamp'], "%Y%m%d%H%M%S")
        return {
            'path': g['path'],
            'type': g['type'],
            'size_bytes': int(g['size']),
            'modified_ts': ts,
            'frames': int(g['frames']),
            'fps': g['fps'],
            'duration': duration
        }
    return None

def extract_artist_title(filename: str) -> Tuple[str, str]:
    parts = filename.split('-')
    if len(parts) < 2:
        return ("Unknown Artist", filename.title())
    artist = parts[0].strip().title()
    title = re.sub(r'\(.*?\)', '', parts[1]).strip().title()
    return artist, title

# Keyboard listener
def keyboard_listener(play_next_event: threading.Event, host: str, port: int, config: Dict[str, Any], threads: Dict[str, threading.Thread]) -> None:
    if IS_WINDOWS:
        logging.warning("Keyboard control disabled on Windows.")
        return
    
    logging.info("Keyboard control: N=Next, S=Stop, L=Logo, I=Stinger, M=Restart Monitor, Q=Quit")
    client = CasparCGClient(host, port)
    logo_on = True

    def get_char() -> str:
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            return sys.stdin.read(1).lower()
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)

    while not stop_event.is_set():
        try:
            c = get_char()
            if c == 'n':
                logging.info("Manual: Play next clip.")
                play_next_event.set()
            elif c == 's':
                logging.info("Manual: Clear all playback.")
                client.send("CLEAR 1")
            elif c == 'l':
                if logo_on:
                    logging.info("Manual: Hiding logo.")
                    client.send('STOP 1-30')
                else:
                    logging.info("Manual: Showing logo.")
                    client.send('MIXER 1-30 FILL 0.04 0.04 0.2 0.19')
                    client.send(f'PLAY 1-30 "{config["logo_path"]}" LOOP')
                logo_on = not logo_on
            elif c == 'i':
                logging.info("Manual: Play stinger.")
                client.send('PLAY 1-30 EMPTY MIX 60')
                time.sleep(2)
                #client.send('MIXER 1 CLEAR')
                client.send('MIXER 1-20 CHROMA GREEN 0.1 0.2 1')
                client.send(f'PLAY 1-20 "{config["stinger_path"]}" AUTO')
                time.sleep(5)
                client.send('MIXER 1-30 FILL 0.04 0.04 0.2 0.19')
                client.send(f'PLAY 1-30 "{config["logo_path"]}" MIX 60 LOOP')
            elif c == 'm':
                logging.info("Manual: Restart Monitor.")
                old_monitor = threads.get('monitor')
                if old_monitor and old_monitor.is_alive():
                    old_monitor.stop()
                    old_monitor.join()
                new_monitor = PlaybackMonitor(host, port, play_next_event)
                new_monitor.start()
                threads["monitor"] = new_monitor
            elif c == 'b':
                logging.info("[Keyboard] Blocking currently playing clip.")
                try:
                    conn = sqlite3.connect('db/media_cache.db')
                    cur = conn.cursor()
                    # Find currently playing clip (you can reuse monitor.layer)
                    client.send('INFO 1-10')
                    response = client.receive_info()
                    xml_part = response.split('\r\n', 1)[-1]
                    root = ET.fromstring(xml_part)
                    file_node = root.find('.//layer_10/foreground/file')
                    if file_node is not None:
                        path_node = file_node.find('path')
                    if path_node is not None:
                        media_path = path_node.text.replace('media/', '').replace('\\', '/')
                        cur.execute("UPDATE media SET blocked = 1 WHERE path = ?", (media_path,))
                        conn.commit()
                        logging.info(f"[Keyboard] Blocked {media_path} from future play.")
                        conn.close()
                except Exception as e:
                    logging.error(f"[Keyboard] Error blocking media: {e}")

            elif c == 'q':
                logging.info("Manual: Emergency quit.")
                stop_event.set()
                os.kill(os.getpid(), signal.SIGINT)
        except Exception as e:
            logging.error(f"\rKeyboard error: {e}")
            time.sleep(1)
# Playback Monitor
class PlaybackMonitor(threading.Thread):
    def __init__(self, host: str, port: int, play_next_event: threading.Event, layer: str = "1-10") -> None:
        super().__init__(daemon=True)
        self.client = CasparCGClient(host, port)
        self.play_next_event = play_next_event
        self.layer = layer
        self.current_time = 0.0
        self.total_time = 0.0
        self.playing = False
        self.lock = threading.Lock()
        self.stop_event = threading.Event()
        self.last_log_time = 0

    def get_playback_status(self) -> Optional[Tuple[float, float]]:
        """Poll CasparCG INFO and return (current_time, total_time) if available."""
        try:
            response = self.client.send_receive_info(f'INFO {self.layer}')
            xml_part = response.split('\r\n', 1)[-1]
            root = ET.fromstring(xml_part)

            file_node = root.find('.//layer_10/foreground/file')
            if file_node is not None:
                times = file_node.findall('time')
                if len(times) >= 2:
                    current_time = float(times[0].text)
                    total_time = float(times[1].text)
                    return current_time, total_time
        except Exception as e:
            monitor_logger.error(f"[Monitor] Error getting playback status: {e}")
        return None

    def check_initial_playback(self) -> bool:
        """Check if a clip is already playing when script starts."""
        playback = self.get_playback_status()
        if playback:
            current_time, total_time = playback
            progress = (current_time / total_time) * 100 if total_time > 0 else 0
            if 0 < progress < 99:
                monitor_logger.info(f"[Startup] Detected existing clip at {progress:.1f}% progress.")
                return True
        return False

    def run(self) -> None:
        monitor_logger.info(f"[Monitor] PlaybackMonitor started on {self.client.host}:{self.client.port} (layer {self.layer})")
        try:
            while not self.stop_event.is_set():
                playback = self.get_playback_status()
                if playback:
                    current_time, total_time = playback
                    with self.lock:
                        self.current_time = current_time
                        self.total_time = total_time

                        playing_now = self.current_time < self.total_time - 0.5
                        if self.playing and not playing_now:
                            monitor_logger.info("[Monitor] Clip finished. Triggering next playback.")
                            self.play_next_event.set()
                        self.playing = playing_now

                    now = time.time()
                    progress = (self.current_time / self.total_time) * 100 if self.total_time > 0 else 0
                    if now - self.last_log_time >= 1:
                        if CONSOLE_ACTIVE:
                            sys.stdout.write(f"\r[Monitor] Progress: {self.current_time:.1f}s / {self.total_time:.1f}s ({progress:.1f}% complete)   ")
                            sys.stdout.flush()
                        self.last_log_time = now
                else:
                    self.playing = False
                time.sleep(1)
        except Exception as e:
            monitor_logger.critical(f"[Monitor] CRASH: {e}")

    def stop(self) -> None:
        self.stop_event.set()


# Media Refresher
class MediaRefresher(threading.Thread):
    def __init__(self, host: str, port: int, db_path: str) -> None:
        super().__init__(daemon=True)
        self.client = CasparCGClient(host, port)
        self.db_path = db_path
        self.stop_event = threading.Event()

    def run(self) -> None:
        while not self.stop_event.is_set():
            self.refresh_media()
            self.stop_event.wait(MEDIA_REFRESH_INTERVAL)

    def refresh_media(self) -> None:
        try:
            conn = sqlite3.connect(self.db_path, timeout=10)
            cur = conn.cursor()
            cur.execute('''CREATE TABLE IF NOT EXISTS media (
                id INTEGER PRIMARY KEY,
                path TEXT UNIQUE,
                type TEXT,
                size_bytes INT,
                modified_ts TIMESTAMP,
                frames INT,
                fps TEXT,
                duration REAL,
                last_seen TIMESTAMP,
                artist TEXT,
                title TEXT,
                release_year INT,
                description TEXT,
                blocked INT DEFAULT 0
            )''')
            cur.execute('''CREATE TABLE IF NOT EXISTS playlog (
                id INTEGER PRIMARY KEY,
                media_id INT,
                started TIMESTAMP
            )''')
            conn.commit()

            response = self.client.send_receive("CLS")
            lines = response.splitlines()
            scanned_paths = set()

            for line in lines:
                refresher_logger.debug(f"\rCLS raw line: {line}")
                parsed = parse_cls_line(line)
                if parsed and parsed['type'] == 'MOVIE':
                    scanned_paths.add(parsed['path'])
                    cur.execute("SELECT id FROM media WHERE path = ?", (parsed['path'],))
                    if not cur.fetchone():
                        artist, title = extract_artist_title(parsed['path'].split('/')[-1])
                        refresher_logger.debug(f"\rAdding new media: {parsed['path']}")
                        cur.execute('''INSERT INTO media (path, type, size_bytes, modified_ts, frames, fps, duration, last_seen,
                                    artist, title, release_year, description)
                                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                                (parsed['path'], parsed['type'], parsed['size_bytes'], parsed['modified_ts'],
                                 parsed['frames'], parsed['fps'], parsed['duration'], datetime.utcnow(),
                                 artist, title, None, None))

            # Delete missing files
            cur.execute("SELECT path FROM media")
            existing_paths = {row[0] for row in cur.fetchall()}
            missing_paths = existing_paths - scanned_paths
            for path in missing_paths:
                refresher_logger.debug(f"\rDeleting missing media: {path}")
                cur.execute("DELETE FROM media WHERE path = ?", (path,))

            conn.commit()
            conn.close()
            refresher_logger.info("\rMedia refresh completed.")
        except sqlite3.OperationalError as e:
            refresher_logger.error(f"\rSQLite error: {e}")
            time.sleep(1)
            self.refresh_media()

    def stop(self) -> None:
        self.stop_event.set()
# Playback Manager
class PlaybackManager(threading.Thread):
    def __init__(self, host: str, port: int, monitor: PlaybackMonitor, db_path: str, config: Dict[str, Any], play_next_event: threading.Event) -> None:
        super().__init__(daemon=True)
        self.client = CasparCGClient(host, port)
        self.monitor = monitor
        self.db_path = db_path
        self.config = config
        self.stop_event = threading.Event()
        self.play_next_event = play_next_event
        self.track_counter = 0
        self.stinger_interval = config.get('stinger_interval', 5)
        self.stinger_path = config.get('stinger_path')


    def run(self) -> None:
        self.setup_logo()
        while not self.stop_event.is_set():
            playback_logger.debug("Waiting for play_next event...")
            self.play_next_event.wait()
            self.play_next_event.clear()

            if self.stop_event.is_set():
                break

            clip = self.choose_clip()
            if not clip:
                playback_logger.warning("No clip found to play.")
                time.sleep(5)
                continue

            media_id, path = clip
            self.play_clip(media_id, path)

    def setup_logo(self) -> None:
        self.client.send('MIXER 1-30 FILL 0.04 0.04 0.2 0.19')
        self.client.send(f'PLAY 1-30 "{self.config["logo_path"]}" LOOP')

    def choose_clip(self) -> Optional[Tuple[int, str]]:
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cutoff_track = datetime.utcnow().timestamp() - ANTI_REPEAT_SECONDS
        
        cur.execute("""
            SELECT m.id, m.path
            FROM media m
            LEFT JOIN (
                SELECT media_id, MAX(strftime('%s', started)) AS last_played
                FROM playlog
                GROUP BY media_id
            ) p ON m.id = p.media_id
            WHERE m.path LIKE 'ROCK MUSIC/%'
              AND (last_played IS NULL OR last_played < ?)
              AND (m.blocked IS NULL OR m.blocked = 0)
            COLLATE NOCASE
        """, (cutoff_track,))
        eligible = cur.fetchall()

        if not eligible:
            playback_logger.warning("\rNo eligible clips found. Falling back to any clip.")
            cur.execute("""
                SELECT id, path
                FROM media 
                WHERE path LIKE 'ROCK MUSIC/%'
                 AND (block IS NULL or blocked = 0)
                COLLATE NOCASE
            """)
            eligible = cur.fetchall()

        
        conn.close()
        if not eligible:
            playback_logger.error("[PlaybackManager] No Clips Available for playback")
            return None
        media_id, path = random.choice(eligible)
        playback_logger.info(f"[PlaybackManager] Selected Clip: {path}")
        return media_id, path


    def play_clip(self, media_id: int, path: str) -> None:
        self.client.send(f'PLAY 1-10 "{path}" MIX {self.config["mix_duration"]}')

        conn = sqlite3.connect(self.db_path)
        conn.execute("INSERT INTO playlog (media_id, started) VALUES (?, ?)", (media_id, datetime.utcnow()))
        conn.commit()

        # Try to get metadata
        cur = conn.cursor()
        cur.execute("SELECT artist, title FROM media WHERE id = ?", (media_id,))
        row = cur.fetchone()
        if row and row[0] and row[1]:
            artist, title = row
        else:
            artist, title = extract_artist_title(path.split('/')[-1])
        conn.close()

        banner_data = json.dumps({"artist": artist, "song": title})
        escaped_banner_data = json.dumps(banner_data)
        playback_logger.info(f"{banner_data}")
        playback_logger.info(f"{escaped_banner_data}")
        #self.client.send(f'CG UPDATE 1 {escaped_banner_data}')
        self.client.send(f'CG 1 ADD 1 {self.config["now_play_name"]} 1 {escaped_banner_data}')
        #playback_logger.debug(f"\rCG 1-{self.config["layer"]} ADD 1 {self.config["now_play_name"]} 1 {escaped_banner_data}")
        playback_logger.info(f"\rNow playing: {artist} - {title}")
        self.track_counter += 1
        if self.track_counter >= self.stinger_interval:
            playback_logger.info("\rTriggering automatic stinger playback.")
            self.client.send('PLAY 1-30 EMPTY MIX 30')
            time.sleep(1)
            #client.send('MIXER 1 CLEAR')
            self.client.send('MIXER 1-20 CHROMA GREEN 0.1 0.2 1')
            self.client.send(f'PLAY 1-20 "{self.config["stinger_path"]}" AUTO')
            time.sleep(5)
            self.client.send('MIXER 1-30 FILL 0.04 0.04 0.2 0.19')
            self.client.send(f'PLAY 1-30 "{self.config["logo_path"]}" MIX 30 LOOP')
            self.track_counter = 0

    def stop(self) -> None:
        self.stop_event.set()

# Watchdog
def watchdog(threads: Dict[str, threading.Thread], host: str, port: int, db_path: str, config: Dict[str, Any], play_next_event: threading.Event) -> None:
    while not stop_event.is_set():
        for name, thread in list(threads.items()):
            if not thread.is_alive() and not stop_event.is_set():
                logging.error(f"\rThread {name} stopped! Restarting...")
                if name == "monitor":
                    new_thread = PlaybackMonitor(host, port, play_next_event)
                elif name == "refresher":
                    new_thread = MediaRefresher(host, port, db_path)
                elif name == "playback":
                    new_thread = PlaybackManager(host, port, threads["monitor"], db_path, config, play_next_event)
                else:
                    continue
                new_thread.start()
                threads[name] = new_thread
        time.sleep(5)

# Main function
def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', default='config.ini', help='Path to config file')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging to console')
    parser.add_argument('--no-keyboard', action='store_true', help='Disable keyboard control')
    args = parser.parse_args()

    config = configparser.ConfigParser()
    config.read(args.config)

    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format='%(asctime)s %(levelname)s:%(message)s',
        handlers=[logging.StreamHandler(),TimedRotatingFileHandler('logs/automation.log', when='midnight', backupCount=7)
        ]
    )
    disable_keyboard = args.no_keyboard or not sys.stdin.isatty() or IS_WINDOWS
    
    amcp_host = config.get('amcp', 'host')
    amcp_port = config.getint('amcp', 'port')

    playback_conf = {
        'mix_duration': config.getint('playback', 'mix_duration'),
        'now_play_name': config.get('playback', 'now_play_name'),
        'stinger_interval': config.getint('playback', 'stinger_interval'),
        'logo_path': config.get('playback', 'logo_path'),
        'stinger_path': config.get('playback', 'stinger_path'),
        'layer': config.getint('banner', 'layer'),
        'banner_duration_sec': config.getint('banner', 'duration_sec')
        
    }

    play_next_event = threading.Event()

    monitor = PlaybackMonitor(amcp_host, amcp_port, play_next_event)
    refresher = MediaRefresher(amcp_host, amcp_port, 'db/media_cache.db')
    playback = PlaybackManager(amcp_host, amcp_port, monitor, 'db/media_cache.db', playback_conf, play_next_event)

    monitor.start()
    refresher.start()
    playback.start()

    threads = {
        "monitor": monitor,
        "refresher": refresher,
        "playback": playback
    }

    threading.Thread(target=watchdog, args=(threads, amcp_host, amcp_port, 'db/media_cache.db', playback_conf, play_next_event), daemon=True).start()
    
    if not disable_keyboard:
        threading.Thread(target=keyboard_listener, args=(play_next_event, amcp_host, amcp_port, {}, threads), daemon=True).start()
    else:
        logging.info("Keyboard listener disabled.")

    play_next_event.set()  # trigger first playback

    def shutdown(signum, frame):
        logging.info("Shutdown requested.")
        stop_event.set()
        try:
            monitor.stop()
        except Exception:
            pass
        try:
            refresher.stop()
        except Exception:
            pass
        try:
            playback.stop()
        except Exception:
            pass

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    try:
        while not stop_event.is_set():
            time.sleep(1)
    except KeyboardInterrupt:
        shutdown(None, None)

    monitor.join()
    refresher.join()
    playback.join()

if __name__ == "__main__":
    main()
