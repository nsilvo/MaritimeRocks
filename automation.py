#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
CasparCG Rock-Music Automation System
Fully refactored to use the backend API for media playback logic,
and report playlog to the backend after playback begins.
Includes keyboard controls for logo, next track, stinger, and quit.
Works cross-platform with fallbacks for Windows where needed.
"""

import argparse
import configparser
import json
import logging
import os
import platform
import re
import signal
import socket
import sys
import threading
import time
import xml.etree.ElementTree as ET
import requests
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler
from typing import Any, Dict, Optional, Tuple

IS_WINDOWS = platform.system() == "Windows"
if not IS_WINDOWS:
    import termios
    import tty

stop_event = threading.Event()
CONSOLE_ACTIVE = sys.stdin.isatty()

def setup_logger(name: str, filename: Optional[str] = None) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    if filename:
        handler = TimedRotatingFileHandler(filename, when='midnight', backupCount=7)
        formatter = logging.Formatter('%(asctime)s %(levelname)s: %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    if name == "console_monitor" and CONSOLE_ACTIVE:
        console = logging.StreamHandler(sys.stdout)
        console.setFormatter(logging.Formatter('[%(asctime)s] %(message)s'))
        logger.addHandler(console)

    logger.propagate = False
    return logger

monitor_logger = setup_logger("monitor", "logs/monitor.log")
playback_logger = setup_logger("playback", "logs/playback.log")
console_logger = setup_logger("console_monitor", "")

class CasparCGClient:
    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self.sock: Optional[socket.socket] = None
        self.lock = threading.Lock()
        self.connect()

    def connect(self):
        while not stop_event.is_set():
            try:
                self.sock = socket.create_connection((self.host, self.port))
                self.sock.settimeout(5)
                logging.info(f"Connected to CasparCG server at {self.host}:{self.port}")
                break
            except Exception as e:
                logging.error(f"Connection failed: {e}, retrying...")
                time.sleep(5)

    def send(self, command: str):
        with self.lock:
            if not self.sock:
                self.connect()
            try:
                self.sock.sendall((command + '\r\n').encode('utf-8'))
            except Exception:
                self.connect()
                self.sock.sendall((command + '\r\n').encode('utf-8'))

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
                    return self.receive_info()
            return buffer.strip()

    def send_receive_info(self, command: str) -> str:
        self.send(command)
        return self.receive_info()

class PlaybackMonitor(threading.Thread):
    def __init__(self, host: str, port: int, play_next_event: threading.Event, layer: str = "1-10"):
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
        try:
            response = self.client.send_receive_info(f'INFO {self.layer}')
            xml_part = response.split('\r\n', 1)[-1]
            root = ET.fromstring(xml_part)
            file_node = root.find('.//layer_10/foreground/file')
            if file_node is not None:
                times = file_node.findall('time')
                if len(times) >= 2:
                    return float(times[0].text), float(times[1].text)
        except Exception as e:
            monitor_logger.error(f"[Monitor] Error getting playback status: {e}")
        return None

    def run(self):
        monitor_logger.info(f"[Monitor] Started on {self.client.host}:{self.client.port} (layer {self.layer})")
        while not self.stop_event.is_set():
            playback = self.get_playback_status()
            if playback:
                current_time, total_time = playback
                with self.lock:
                    self.current_time = current_time
                    self.total_time = total_time
                    playing_now = current_time < total_time - 0.5
                    if self.playing and not playing_now:
                        monitor_logger.info("[Monitor] Clip finished. Triggering next playback.")
                        self.play_next_event.set()
                    self.playing = playing_now

                now = time.time()
                progress = (current_time / total_time) * 100 if total_time > 0 else 0
                if now - self.last_log_time >= 1 and CONSOLE_ACTIVE:
                    sys.stdout.write(f"\r[Monitor] {current_time:.1f}s / {total_time:.1f}s ({progress:.1f}%)   ")
                    sys.stdout.flush()
                    self.last_log_time = now
            else:
                self.playing = False
            time.sleep(1)

    def stop(self):
        self.stop_event.set()

class PlaybackManager(threading.Thread):
    def __init__(self, host: str, port: int, monitor: PlaybackMonitor, config: Dict[str, Any], play_next_event: threading.Event):
        super().__init__(daemon=True)
        self.client = CasparCGClient(host, port)
        self.monitor = monitor
        self.config = config
        self.stop_event = threading.Event()
        self.play_next_event = play_next_event
        self.track_counter = 0
        self.stinger_interval = config.get('stinger_interval', 5)
        self.stinger_path = config.get('stinger_path')
        self.logo_on = True
        self.current_clip = None

    def run(self):
        self.setup_logo()
        while not self.stop_event.is_set():
            self.play_next_event.wait()
            self.play_next_event.clear()

            if self.stop_event.is_set():
                break

            if not self.current_clip:
                self.current_clip = self.fetch_next_clip()
            if not self.current_clip:
                playback_logger.warning("No clip returned from API.")
                time.sleep(5)
                continue

            self.play_clip(self.current_clip)
            self.log_play_event(self.current_clip)
            self.current_clip = None

    def setup_logo(self):
        self.client.send('MIXER 1-30 FILL 0.04 0.04 0.2 0.19')
        self.client.send(f'PLAY 1-30 "{self.config["logo_path"]}" LOOP')

    def fetch_next_clip(self) -> Optional[Dict[str, Any]]:
        try:
            resp = requests.get("http://localhost:8000/next_clip")
            if resp.status_code == 200:
                return resp.json()
            playback_logger.warning(f"API responded with {resp.status_code}: {resp.text}")
        except Exception as e:
            playback_logger.error(f"Error calling backend API: {e}")
        return None

    def play_clip(self, clip: Dict[str, Any]):
        self.client.send(f'PLAY 1-10 "{clip["path"]}" MIX {self.config["mix_duration"]}')
        banner_data = json.dumps({"artist": clip.get("artist", ""), "song": clip.get("title", "")})
        escaped = json.dumps(banner_data)
        self.client.send(f'CG 1 ADD 1 {self.config["now_play_name"]} 1 {escaped}')
        playback_logger.info(f"Now playing: {clip.get('artist', 'Unknown')} - {clip.get('title', '')}")
        self.track_counter += 1

        if self.track_counter >= self.stinger_interval:
            self.client.send('PLAY 1-30 EMPTY MIX 30')
            time.sleep(1)
            self.client.send('MIXER 1-20 CHROMA GREEN 0.1 0.2 1')
            self.client.send(f'PLAY 1-20 "{self.config["stinger_path"]}" AUTO')
            time.sleep(5)
            self.client.send('MIXER 1-30 FILL 0.04 0.04 0.2 0.19')
            self.client.send(f'PLAY 1-30 "{self.config["logo_path"]}" MIX 30 LOOP')
            self.track_counter = 0

    def log_play_event(self, clip: Dict[str, Any]):
        try:
            with self.monitor.lock:
                duration = self.monitor.total_time
                
            payload = {
                "media_id": clip["id"],
                "started": datetime.utcnow().isoformat(),
                "duration": round(duration, 2) if duration else None 
                }
            
            resp = requests.post("http://localhost:8000/log_play", json=payload)
            if resp.status_code != 200:
                playback_logger.warning(f"Failed to log play event: {resp.text}")
        except Exception as e:
            playback_logger.error(f"Error sending playlog: {e}")

    def stop(self):
        self.stop_event.set()


def keyboard_listener(play_next_event: threading.Event, playback: PlaybackManager):
    if IS_WINDOWS or not CONSOLE_ACTIVE:
        logging.info("Keyboard input disabled.")
        return

    logging.info("Keyboard: N=Next, S=Stop, L=Logo, I=Stinger, Q=Quit")
    def get_char():
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            return sys.stdin.read(1).lower()
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)

    while not stop_event.is_set():
        c = get_char()
        if c == 'n':
            play_next_event.set()
        elif c == 's':
            playback.client.send("CLEAR 1")
        elif c == 'l':
            if playback.logo_on:
                playback.client.send('STOP 1-30')
            else:
                playback.client.send('MIXER 1-30 FILL 0.04 0.04 0.2 0.19')
                playback.client.send(f'PLAY 1-30 "{playback.config["logo_path"]}" LOOP')
            playback.logo_on = not playback.logo_on
        elif c == 'i':
            playback.client.send('PLAY 1-30 EMPTY MIX 60')
            time.sleep(2)
            playback.client.send('MIXER 1-20 CHROMA GREEN 0.1 0.2 1')
            playback.client.send(f'PLAY 1-20 "{playback.config["stinger_path"]}" AUTO')
            time.sleep(5)
            playback.client.send('MIXER 1-30 FILL 0.04 0.04 0.2 0.19')
            playback.client.send(f'PLAY 1-30 "{playback.config["logo_path"]}" MIX 60 LOOP')
        elif c == 'q':
            stop_event.set()
            os.kill(os.getpid(), signal.SIGINT)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', default='config.ini')
    args = parser.parse_args()

    config = configparser.ConfigParser()
    config.read(args.config)

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(levelname)s:%(message)s',
        handlers=[logging.StreamHandler(), TimedRotatingFileHandler('logs/automation.log', when='midnight', backupCount=7)]
    )

    amcp_host = config.get('amcp', 'host')
    amcp_port = config.getint('amcp', 'port')

    playback_conf = {
        'mix_duration': config.getint('playback', 'mix_duration'),
        'now_play_name': config.get('playback', 'now_play_name'),
        'stinger_interval': config.getint('playback', 'stinger_interval'),
        'logo_path': config.get('playback', 'logo_path'),
        'stinger_path': config.get('playback', 'stinger_path'),
    }

    play_next_event = threading.Event()
    monitor = PlaybackMonitor(amcp_host, amcp_port, play_next_event)
    playback = PlaybackManager(amcp_host, amcp_port, monitor, playback_conf, play_next_event)

    monitor.start()
    playback.start()
    threading.Thread(target=keyboard_listener, args=(play_next_event, playback), daemon=True).start()

    def shutdown(signum, frame):
        logging.info("Shutdown requested.")
        stop_event.set()
        monitor.stop()
        playback.stop()

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    try:
        while not stop_event.is_set():
            time.sleep(1)
    except KeyboardInterrupt:
        shutdown(None, None)

    monitor.join()
    playback.join()

if __name__ == "__main__":
    main()