#!/usr/bin/env python3
"""
weekly_loader.py

Fetch (or reuse) the latest Ofcom WTR.csv once per day and merge its contents into Postgres.

 1. Cache WTR.csv locally (only re-download if older than 1 day).
 2. Load into a temporary staging table with dynamic column matching.
 3. Upsert/merge into the main 'frequencies' table, skipping rows with invalid or missing data,
    and delete stale rows.
"""

import os
import time
import urllib.request
import psycopg2
import psycopg2.extras
import pandas as pd

# --- Configuration ---
WTR_URL      = "https://static.ofcom.org.uk/static/radiolicensing/html/register/WTR.csv"
CACHE_FILE   = "wtr_cached.csv"
CACHE_TTL    = 86400   # 1 day in seconds

DEFAULT_DB   = "postgres"
TARGET_DB    = "frequency_db"
DB_USER      = "frequency_user"
DB_PASSWORD  = "PeckhamClaphamHackney"
DB_HOST      = "localhost"
DB_PORT      = 5432

MAIN_TABLE   = "frequencies"
TEMP_TABLE   = "frequencies_temp"

# Expected WTR CSV headers (original form). We'll snake_case them.
WTR_COLUMNS = [
    "Licence Number",           "License Issue Date",
    "SID_LAT_N_S",              "SID_LAT_DEG",
    "SID_LAT_MIN",              "SID_LAT_SEC",
    "SID_LONG_E_W",             "SID_LONG_DEG",
    "SID_LONG_MIN",             "SID_LONG_SEC",
    "NGR",                      "Frequency (Hz)",
    "Station Type",             "Channel Width (Hz)",
    "Height Above Sea Level",   "Antenna ERP",
    "Antenna ERP Unit",         "Antenna ERP Type",
    "Antenna Type",             "Antenna Gain",
    "Antenna AZIMUTH",          "Horizontal Elements",
    "Vertical Elements",        "Antenna Height",
    "Antenna Location",         "EFL_UPPER_LOWER",
    "Antenna Direction",        "Antenna Elevation",
    "Antenna Polarisation",     "Antenna Name",
    "Feeding Loss",             "Fade Margin",
    "Emission Code",            "Licencee Surname",
    "Licencee First Name",      "Licencee Company",
    "Status",                   "Tradeable",
    "Publishable",              "Product Code",
    "Product Description",      "Latitude(Deg)",
    "Longitude(Deg)"
]

def snake_case(col: str) -> str:
    """
    Convert a header string into snake_case:
      - Lowercase
      - Remove parentheses
      - Replace spaces/slashes/hyphens with underscores
      - Collapse double underscores
    """
    return (
        col.strip()
           .lower()
           .replace("(", "")
           .replace(")", "")
           .replace("/", "_")
           .replace(" ", "_")
           .replace("-", "_")
           .replace("__", "_")
    )

def connect(dbname: str):
    """Open a psycopg2 connection using our application user."""
    return psycopg2.connect(
        dbname=dbname,
        user=DB_USER,
        password=DB_PASSWORD,
        host=DB_HOST,
        port=DB_PORT
    )

def ensure_cached_csv() -> str:
    """
    Ensure WTR.csv is cached locally. If CACHE_FILE is older than 1 day (CACHE_TTL),
    re-download. Return the local path.
    """
    if os.path.exists(CACHE_FILE):
        age = time.time() - os.path.getmtime(CACHE_FILE)
        if age < CACHE_TTL:
            print(f"Using cached CSV (age {age:.0f}s < {CACHE_TTL}s).")
            return CACHE_FILE

    print("Downloading latest WTR.csv from Ofcom...")
    urllib.request.urlretrieve(WTR_URL, CACHE_FILE)
    print(f"Downloaded and cached as {CACHE_FILE}.")
    return CACHE_FILE

def prepare_temp_table(conn):
    """
    Drop & recreate TEMP_TABLE with all WTR_COLUMNS snake_cased (TEXT except lat/long)
    plus a GEOGRAPHY geom column.
    """
    cur = conn.cursor()
    cur.execute(f"DROP TABLE IF EXISTS {TEMP_TABLE};")

    # Build DDL columns: latitudedeg/longitudedeg as DOUBLE PRECISION, else TEXT
    ddl_cols = []
    for orig in WTR_COLUMNS:
        col_snake = snake_case(orig)
        if col_snake in ("latitudedeg", "longitudedeg"):
            ddl_cols.append(f"{col_snake} DOUBLE PRECISION")
        else:
            ddl_cols.append(f"{col_snake} TEXT")
    ddl_cols.append("geom GEOGRAPHY(Point,4326)")
    ddl = f"CREATE TABLE {TEMP_TABLE} ({', '.join(ddl_cols)});"

    print("Creating temporary table for WTR data...")
    cur.execute(ddl)
    conn.commit()
    cur.close()

def load_csv_into_temp(conn, csv_path):
    """
    Read WTR.csv into Pandas, match headers dynamically via snake_case,
    select present columns, bulk-insert into TEMP_TABLE, then populate geom.
    """
    print("Reading CSV into Pandas (dynamic column matching)...")
    df = pd.read_csv(csv_path, dtype=str)

    # Map snake_case(actual_header) -> actual_header
    actual_cols = list(df.columns)
    snake_to_actual = {snake_case(c): c for c in actual_cols}

    # Determine which expected columns are present
    insert_cols = []
    missing = []
    for orig in WTR_COLUMNS:
        s = snake_case(orig)
        if s in snake_to_actual:
            insert_cols.append((s, snake_to_actual[s]))
        else:
            missing.append(orig)

    if missing:
        print("Warning: Missing expected columns:")
        for m in missing:
            print("  -", m)
        print("Proceeding with available columns only.")

    # Build staging DataFrame
    data = {}
    for col_snake, col_actual in insert_cols:
        if col_snake in ("latitudedeg", "longitudedeg"):
            data[col_snake] = pd.to_numeric(df[col_actual], errors="coerce")
        else:
            data[col_snake] = df[col_actual]
    staged = pd.DataFrame(data)
    staged["geom"] = None

    # Bulk-insert into TEMP_TABLE
    cols = list(staged.columns)
    cols_sql = ",".join(cols)
    records = staged.to_dict(orient="records")
    tuples = [tuple(rec[c] for c in cols) for rec in records]

    cur = conn.cursor()
    sql = f"INSERT INTO {TEMP_TABLE} ({cols_sql}) VALUES %s"
    print(f"Inserting {len(tuples)} rows into {TEMP_TABLE}...")
    psycopg2.extras.execute_values(cur, sql, tuples, page_size=1000)
    conn.commit()

    # Populate geom if lat/lon present
    if "latitudedeg" in cols and "longitudedeg" in cols:
        print("Populating geom in TEMP_TABLE...")
        cur.execute(f"""
          UPDATE {TEMP_TABLE}
          SET geom = ST_SetSRID(
                       ST_MakePoint(longitudedeg, latitudedeg),
                       4326
                     )::geography
          WHERE latitudedeg IS NOT NULL
            AND longitudedeg IS NOT NULL;
        """)
        conn.commit()
    else:
        print("No latitudedeg/longitudedeg → skipping geom population.")
    cur.close()

def prepare_main_table(conn):
    """
    Ensure MAIN_TABLE exists with correct schema & indexes. If PostGIS is missing,
    raise an error prompting manual installation. Also ensure the unique constraint.
    """
    cur = conn.cursor()

    # 1) Verify PostGIS is enabled
    try:
        cur.execute("SELECT postgis_full_version();")
    except psycopg2.Error:
        raise RuntimeError(
            "PostGIS not enabled in 'frequency_db'.\n"
            "Please run as superuser:\n"
            "  CREATE EXTENSION IF NOT EXISTS postgis;"
        )

    # 2) Create MAIN_TABLE if missing (with required columns)
    cur.execute(f"""
      CREATE TABLE IF NOT EXISTS {MAIN_TABLE} (
        id SERIAL PRIMARY KEY,
        licence_number    TEXT,
        freq_hz           BIGINT     NOT NULL,
        station_type      CHAR(1),
        prod_desc         TEXT,
        licencee_company  TEXT       NOT NULL,
        antenna_loc       TEXT,
        lat               DOUBLE PRECISION,
        lon               DOUBLE PRECISION,
        geom              GEOGRAPHY(Point,4326)
      );
    """)
    conn.commit()

    # 3) Add any missing columns
    required_cols = [
        ("licence_number",   "TEXT"),
        ("freq_hz",          "BIGINT NOT NULL"),
        ("station_type",     "CHAR(1)"),
        ("prod_desc",        "TEXT"),
        ("licencee_company", "TEXT NOT NULL"),
        ("antenna_loc",      "TEXT"),
        ("lat",              "DOUBLE PRECISION"),
        ("lon",              "DOUBLE PRECISION"),
        ("geom",             "GEOGRAPHY(Point,4326)")
    ]
    for col_name, col_type in required_cols:
        cur.execute(f"""
          ALTER TABLE {MAIN_TABLE}
          ADD COLUMN IF NOT EXISTS {col_name} {col_type};
        """)
    conn.commit()

    # 4) Ensure unique constraint on (freq_hz, licencee_company)
    try:
        cur.execute(f"""
          ALTER TABLE {MAIN_TABLE}
          ADD CONSTRAINT unique_freq_company UNIQUE(freq_hz, licencee_company);
        """)
        conn.commit()
    except (psycopg2.errors.DuplicateObject, psycopg2.errors.DuplicateTable):
        conn.rollback()

    # 5) Create indexes on geom and on (prod_desc, station_type)
    cur.execute(f"CREATE INDEX IF NOT EXISTS idx_{MAIN_TABLE}_geom ON {MAIN_TABLE} USING GIST (geom);")
    cur.execute(f"CREATE INDEX IF NOT EXISTS idx_{MAIN_TABLE}_filter ON {MAIN_TABLE}(prod_desc, station_type);")
    conn.commit()

    cur.close()

def merge_temp_into_main(conn):
    """
    Upsert from TEMP_TABLE into MAIN_TABLE, skipping any rows where:
      - frequency_hz is not purely digits (using regex),
      - or licencee_company is NULL or empty.
    Then delete stale MAIN_TABLE rows (same filter).
    """
    cur = conn.cursor()

    # Upsert only valid rows
    cur.execute(f"""
      INSERT INTO {MAIN_TABLE} (
        licence_number,
        freq_hz,
        station_type,
        prod_desc,
        licencee_company,
        antenna_loc,
        lat,
        lon,
        geom
      )
      SELECT
        licence_number,
        CAST(frequency_hz AS BIGINT),
        station_type,
        product_description::TEXT,
        licencee_company,
        antenna_location,
        latitudedeg,
        longitudedeg,
        geom
      FROM {TEMP_TABLE}
      WHERE frequency_hz ~ '^[0-9]+$'
        AND licencee_company IS NOT NULL
        AND licencee_company <> ''
      ON CONFLICT (freq_hz, licencee_company)
      DO UPDATE SET
        licence_number   = EXCLUDED.licence_number,
        station_type     = EXCLUDED.station_type,
        prod_desc        = EXCLUDED.prod_desc,
        antenna_loc      = EXCLUDED.antenna_loc,
        lat              = EXCLUDED.lat,
        lon              = EXCLUDED.lon,
        geom             = EXCLUDED.geom
      ;
    """)
    conn.commit()

    # Delete any rows no longer present (with valid keys)
    cur.execute(f"""
      DELETE FROM {MAIN_TABLE}
      WHERE (freq_hz, licencee_company) NOT IN (
        SELECT CAST(frequency_hz AS BIGINT), licencee_company
        FROM {TEMP_TABLE}
        WHERE frequency_hz ~ '^[0-9]+$'
          AND licencee_company IS NOT NULL
          AND licencee_company <> ''
      );
    """)
    conn.commit()

    cur.close()

def main():
    # 1) Ensure local CSV cache is fresh (≤ 1 day old)
    csv_path = ensure_cached_csv()

    # 2) Create TARGET_DB if missing (connect to DEFAULT_DB)
    conn_default = connect(DEFAULT_DB)
    conn_default.autocommit = True
    cur = conn_default.cursor()
    cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (TARGET_DB,))
    if not cur.fetchone():
        print(f"Creating database '{TARGET_DB}'…")
        cur.execute(f"CREATE DATABASE {TARGET_DB} OWNER {DB_USER};")
    cur.close()
    conn_default.close()

    # 3) Connect to TARGET_DB as frequency_user
    conn = connect(TARGET_DB)
    conn.autocommit = False

    # 4) Prepare MAIN_TABLE (PostGIS must already be enabled)
    prepare_main_table(conn)

    # 5) Prepare & load TEMP_TABLE
    prepare_temp_table(conn)
    load_csv_into_temp(conn, csv_path)

    # 6) Merge TEMP_TABLE into MAIN_TABLE (skipping invalid rows)
    merge_temp_into_main(conn)

    conn.close()

    print("Weekly load complete: MAIN_TABLE synced with latest WTR.csv.")

if __name__ == "__main__":
    main()
