#!/usr/bin/env python3
"""
frequency_list.py

Flask app serving frequency data and bookmarks, now querying the Postgres
table `frequencies` with snake_cased columns and a SERIAL id PK.
"""

from flask import Flask, request, jsonify, render_template
import os, json, math, re, psycopg2, psycopg2.extras

# --- Configuration ---
BOOKMARKS_PATH = "/var/lib/openwebrx/bookmarks.json"

DB_NAME     = "frequency_db"
DB_USER     = "frequency_user"
DB_PASSWORD = "PeckhamClaphamHackney"
DB_HOST     = "localhost"
DB_PORT     = 5432

# OfW84 modulation‐type ↔ human name
MODULATION_MAP = {
    'N': 'Unmodulated (Carrier)',
    'A': 'AM (Double Sideband)',
    'H': 'SSB-Full Carrier',
    'R': 'SSB-Reduced Carrier',
    'J': 'SSB-Suppressed Carrier',
    'B': 'Independent Sidebands',
    'C': 'Vestigial Sideband',
    'F': 'FM',
    'G': 'PM',
    'D': 'AM + FM',
    'P': 'Pulse (Unmodulated)',
    'K': 'Pulse-AM',
    'L': 'Pulse-Width Modulation',
    'M': 'Pulse-Position Modulation',
    'Q': 'Pulse-PM',
    'V': 'Pulse-Combination',
    'W': 'Combination (AM/PM/Pulse)',
    'X': 'Other'
}

app = Flask(__name__, template_folder=".")

def get_db_connection():
    return psycopg2.connect(
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        host=DB_HOST,
        port=DB_PORT
    )

def haversine(lat1, lon1, lat2, lon2):
    R = 3958.8
    φ1, φ2 = math.radians(lat1), math.radians(lat2)
    dφ = math.radians(lat2 - lat1)
    dλ = math.radians(lon2 - lon1)
    a = math.sin(dφ/2)**2 + math.cos(φ1)*math.cos(φ2)*math.sin(dλ/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

def get_modulation(emission_code):
    if not isinstance(emission_code, str):
        return 'Unknown'
    m = re.match(r'^\d+[HhKkMmGg]\d*([A-Za-z])', emission_code)
    if m:
        mod_char = m.group(1).upper()
    else:
        tail = re.sub(r'^[0-9]+[HhKkMmGg][0-9]*', '', emission_code)
        mod_char = tail[:1].upper() if tail else ''
    return MODULATION_MAP.get(mod_char, 'Unknown')

def load_filtered_data(center_lat, center_lon, radius_miles):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    # Use snake_case column names
    cur.execute("""
        SELECT
          id,
          frequency_hz    AS freq,
          emission_code   AS emission_code,
          licencee_company  AS company,
          antenna_location  AS location,
          latitudedeg     AS lat,
          longitudedeg    AS lon
        FROM frequencies
        WHERE product_description = %s
          AND station_type        = %s
    """, ('BR Tech Assigned', 'T'))
    records = cur.fetchall()
    cur.close()
    conn.close()

    out = []
    seen = set()
    for r in records:
        try:
            row_id  = r['id']
            freq_hz = int(r['freq'])
            comp    = (r['company'] or '').strip()
            key     = (freq_hz, comp)
            if key in seen:
                continue
            plat, plon = float(r['lat']), float(r['lon'])
            dist = haversine(center_lat, center_lon, plat, plon)
            if dist > radius_miles:
                continue
            seen.add(key)
            out.append({
                "id": row_id,
                "Frequency (Hz)": freq_hz,
                "Distance": round(dist, 2),
                "modulation": get_modulation(r['emission_code']),
                "Licencee Company": comp,
                "Antenna Location": r['location'] or '',
                "Latitude(Deg)": plat,
                "Longitude(Deg)": plon
            })
        except Exception:
            continue
    return out

def load_bookmarks():
    if not os.path.exists(BOOKMARKS_PATH):
        return []
    try:
        return json.load(open(BOOKMARKS_PATH))
    except:
        return []

def save_bookmarks(bms):
    try:
        json.dump(bms, open(BOOKMARKS_PATH, "w"), indent=2)
        return True
    except:
        return False

@app.route("/")
def index():
    return render_template("template.html")

@app.route("/bookmarks")
def bookmarks_page():
    return render_template("bookmarks.html")

@app.route("/api/data")
def api_data():
    try:
        lat = float(request.args.get("lat", 52.2405))
        lon = float(request.args.get("lon", -0.9027))
        rad = float(request.args.get("radius", 5))
        rows = load_filtered_data(lat, lon, rad)
        return jsonify(rows=rows)
    except Exception as e:
        app.logger.exception("Error in /api/data")
        return jsonify(rows=[], error=str(e)), 200

@app.route("/api/bookmarks")
def api_bookmarks():
    return jsonify(load_bookmarks())

@app.route("/add_bookmarks", methods=["POST"])
def add_bookmarks():
    new_items = request.json
    if not isinstance(new_items, list):
        return jsonify(error="Expected list"), 400

    bms  = load_bookmarks()
    seen = {round(b.get("frequency", 0), 6) for b in bms}
    added = 0

    conn = get_db_connection()
    cur  = conn.cursor()

    for item in new_items:
        try:
            # Prefer id lookup
            if item.get("id") is not None:
                cur.execute("""
                  SELECT frequency_hz, emission_code, licencee_company
                  FROM frequencies WHERE id = %s
                """, (int(item["id"]),))
                rec = cur.fetchone()
                if not rec:
                    continue
                freq_hz, emission_code, comp = rec
            else:
                # fallback by freq+company
                raw = float(item.get("freq", 0))
                freq_hz = round(raw * 1e6) if raw < 1e6 else round(raw)
                comp = item.get("name", "").strip()
                cur.execute("""
                  SELECT emission_code FROM frequencies
                  WHERE frequency_hz = %s AND licencee_company = %s
                  LIMIT 1
                """, (freq_hz, comp))
                rec = cur.fetchone()
                emission_code = rec[0] if rec else ""

            if not freq_hz or freq_hz in seen:
                continue

            human = get_modulation(emission_code)
            if human.lower().startswith("pulse"):
                mode = "dmr"
            elif human == "FM":
                mode = "nfm"
            elif human.startswith("AM"):
                mode = "am"
            else:
                mode = "nfm"

            bms.append({
                "name": comp or item.get("name","Unnamed"),
                "frequency": int(freq_hz),
                "modulation": mode,
                "underlying": "",
                "description": "",
                "scannable": True
            })
            seen.add(freq_hz)
            added += 1

        except Exception:
            continue

    cur.close()
    conn.close()

    if not save_bookmarks(bms):
        return jsonify(error="Failed to write bookmarks"), 500
    return jsonify(added=added)

@app.route("/save_bookmarks", methods=["POST"])
def save_bms():
    data = request.json
    if not isinstance(data, list):
        return jsonify(error="Expected list"), 400
    ok = save_bookmarks(data)
    return jsonify(success=ok)

if __name__ == "__main__":
    app.run(debug=True, port=5000)
