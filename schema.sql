CREATE TABLE media (
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
                description TEXT
            , blocked INT DEFAULT 0, category TEXT);
CREATE TABLE playlog (
                id INTEGER PRIMARY KEY,
                media_id INT,
                started TIMESTAMP
            );
CREATE INDEX idx_playlog_started ON playlog(started);
CREATE INDEX idx_playlog_media_id ON playlog(media_id);
