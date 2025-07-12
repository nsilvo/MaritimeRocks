#!/usr/bin/env python3
"""
data_loader.py

Full-reload loader for `frequencies.csv` into Postgres, connecting as
the dedicated user `frequency_user`. Now adds an `id SERIAL PRIMARY KEY`
to the `frequencies` table.

Usage:
    python3 data_loader.py
"""

import os
import psycopg2
import psycopg2.extras
import pandas as pd

# --- Configuration ---
DEFAULT_DB     = "postgres"
TARGET_DB      = "frequency_db"
DB_USER        = "frequency_user"
DB_PASSWORD    = "PeckhamClaphamHackney"
DB_HOST        = "localhost"
DB_PORT        = 5432

CSV_FILE       = "frequencies.csv"
TABLE_NAME     = "frequencies"

def snake_case(col: str) -> str:
    """Convert CSV header to snake_case identifier."""
    return (
        col.strip().lower()
           .replace("(", "").replace(")", "")
           .replace("/", "_")
           .replace(" ", "_")
           .replace("-", "_")
           .replace("__", "_")
    )

def connect(dbname: str):
    """Open a psycopg2 connection using DB_USER and DB_PASSWORD."""
    return psycopg2.connect(
        dbname=dbname,
        user=DB_USER,
        password=DB_PASSWORD,
        host=DB_HOST,
        port=DB_PORT
    )

def create_database():
    """Connect to DEFAULT_DB and create TARGET_DB if needed."""
    # We connect as the app user; ensure it has CREATEDB or pre-grant that
    conn = connect(DEFAULT_DB)
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (TARGET_DB,))
    if not cur.fetchone():
        print(f"Creating database '{TARGET_DB}'...")
        cur.execute(f"CREATE DATABASE {TARGET_DB} OWNER {DB_USER};")
    cur.close()
    conn.close()

def create_table_and_load():
    """Drop & recreate the frequencies table (with PK), then bulk-load CSV."""
    # 1) Read header to get column names
    df_header = pd.read_csv(CSV_FILE, nrows=0)
    orig_cols  = list(df_header.columns)
    columns    = [snake_case(c) for c in orig_cols]

    # 2) Connect to TARGET_DB as frequency_user
    conn = connect(TARGET_DB)
    cur  = conn.cursor()

    # 3) Drop existing table
    cur.execute(f"DROP TABLE IF EXISTS {TABLE_NAME};")

    # 4) Create table with id PK, plus one column per CSV header
    ddl_cols = ["id SERIAL PRIMARY KEY"]
    for col in columns:
        if col in ("latitude_deg", "longitude_deg"):
            ddl_cols.append(f"{col} DOUBLE PRECISION")
        else:
            ddl_cols.append(f"{col} TEXT")
    ddl = f"CREATE TABLE {TABLE_NAME} ({', '.join(ddl_cols)});"

    print("Creating table with columns:")
    print("  id, " + ", ".join(columns))
    cur.execute(ddl)
    conn.commit()

    # 5) Load entire CSV into Pandas, rename, prepare for INSERT
    print("Reading full CSV into memory...")
    df = pd.read_csv(CSV_FILE)
    df.columns = columns
    records    = df.to_records(index=False)
    tuples     = [tuple(rec) for rec in records]

    # 6) Bulk insert via execute_values
    cols_sql = ", ".join(columns)
    sql      = f"INSERT INTO {TABLE_NAME} ({cols_sql}) VALUES %s"
    print(f"Inserting {len(tuples)} rows...")
    psycopg2.extras.execute_values(cur, sql, tuples, page_size=1000)
    conn.commit()

    # 7) Done
    cur.close()
    conn.close()
    print("Data load complete.")

if __name__ == "__main__":
    create_database()
    create_table_and_load()
