-- schema.sql - PostgreSQL schema for Radio Traffic System
-- Supports user auth, multi-station, audio ads, and scheduling

-- Users table: Handles login/auth with roles
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT DEFAULT 'user',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Stations table: Supports multi-station setup
CREATE TABLE IF NOT EXISTS stations (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL
);

-- Adverts table: Stores uploaded commercial metadata
CREATE TABLE IF NOT EXISTS adverts (
    id SERIAL PRIMARY KEY,
    station_id INT REFERENCES stations(id),
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    filename TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Schedules table: Maps ads to specific time slots
CREATE TABLE IF NOT EXISTS schedules (
    id SERIAL PRIMARY KEY,
    station_id INT REFERENCES stations(id),
    time_slot TIME NOT NULL,
    ad_id INT REFERENCES adverts(id),
    position INT NOT NULL  -- position within the break
);
