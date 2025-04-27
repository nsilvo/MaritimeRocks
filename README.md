
# Maritime Rocks Automation

**CasparCG MusicTV Automation Pack**  
Automated music video playback, metadata-driven now-playing graphics, and manual operator control.

---

## Features

- Randomized rock clip playout
- Anti-repeat logic (no repeats within 3 hours)
- Metadata-driven now-playing banners
- Persistent CasparCG connections (separate sockets for playback and media sync)
- Real-time playback monitor (single-line console progress output)
- Manual keyboard control (Next / Stop / Logo Toggle / Stinger / Restart Monitor / Emergency Quit)
- Watchdog system with auto-recovery for failed threads
- Rotating log files for organized debugging

---

## Installation

1. Install Python 3.8 or higher (recommended: Python 3.11 or later).

2. Clone the repository:
```bash
git clone https://github.com/nsilvo/MaritimeRocks.git
cd MaritimeRocks
```

3. Install required Python packages:
```bash
pip install -r requirements.txt
```

4. Edit `config.ini` to match your CasparCG server settings and media folder paths.

---

## Running the Automation

To start the automation:

```bash
python3 automation.py
```

Upon launch, the system will:

- Connect to the CasparCG server.
- Perform a media refresh creating the database file if one doesnt exist
- Begin automated video playback.
- Display metadata-driven now-playing banners. assuming you have one called NOW_PLAYING
- Allow manual operator control via the keyboard. so you can have some fun pushing buttons.

---

## Keyboard Controls

| Key | Action |
|:----|:-------|
| **N** | Play the next random clip immediately |
| **S** | Stop all CasparCG playback |
| **L** | Toggle the permanent logo ON/OFF |
| **I** | Play the stinger manually |
| **M** | Restart the playback monitor thread |
| **Q** | shutdown (stop all threads and exit the script) |

---

## Project Structure

| File | Purpose |
|:-----|:--------|
| `automation.py` | Main automation script |
| `config.ini` | Configuration file for server and playback settings |
| `db/media_cache.db` | Local SQLite database caching media metadata and playback logs |
| `CasparGFX/now_playing.html` | CasparCG HTML5 template for now-playing banners |
| `requirements.txt` | Python dependency list |

---

## Logging

Logs rotate daily and are stored in individual files these all live in the logs directory:

- `automation.log` — main events and system startup
- `playback.log` — playback choices and now-playing updates
- `monitor.log` — real-time playback monitoring
- `refresher.log` — database synchronization activities

Each thread writes to its own log file for clear separation.

---

## Troubleshooting

- **No clips playing**: Verify that the media paths in `config.ini` match your CasparCG media folder.
- **Now-playing banner not showing**: Confirm that `now_playing.html` exists and is correctly linked.
- **Monitor not updating**: Restart the monitor thread manually by pressing `M`.
- **Keyboard controls not responding**: Ensure the script is running interactively in a terminal window.
- **Duplicate song playbacks**: Check that each media file is unique and correctly timestamped.

---

## License

This project is licensed under the MIT License.  
See the [LICENSE](./LICENSE) file for more details.

---

## Notes

- Designed for CasparCG Server 2.3 and later.
- Default stage layout assumes 1080p resolution but can be adjusted.
- Intended primarily for music automation, but easily customizable for any genre or event.
