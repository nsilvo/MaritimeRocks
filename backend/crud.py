from sqlalchemy import Table, Column, Integer, String, Float, MetaData, select, update, delete, func, text
from database import engine
from models import MediaUpdate

metadata = MetaData()

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
    Column("category", String, nullable=True)
)

playlog = Table(
    "playlog", metadata,
    autoload_with=engine
)

def get_all_media(category: str = None):
    stmt = select(media)
    if category:
        stmt = stmt.where(media.c.category == category)
    stmt = stmt.limit(100)
    with engine.connect() as conn:
        result = conn.execute(stmt)
        return [dict(row._mapping) for row in result]


def update_media_entry(media_id: int, data: MediaUpdate):
    stmt = (
        update(media)
        .where(media.c.id == media_id)
        .values(**data.dict(exclude_unset=True))
    )
    with engine.begin() as conn:
        conn.execute(stmt)

def delete_media_entry(media_id: int):
    stmt = delete(media).where(media.c.id == media_id)
    with engine.begin() as conn:
        conn.execute(stmt)

def get_dashboard_stats():
    with engine.connect() as conn:
        total = conn.execute(select(func.count()).select_from(media)).scalar()
        blocked = conn.execute(select(func.count()).select_from(media).where(media.c.blocked == 1)).scalar()
        
        category_counts = conn.execute(
            select(media.c.category, func.count()).group_by(media.c.category)
        ).all()
        category_counts = {row[0] or "Uncategorized": row[1] for row in category_counts}

        # NEW: Join playlog with media
        recent_played = conn.execute(
            text("""
            SELECT 
                playlog.id AS playlog_id,
                media.id AS media_id,
                media.artist,
                media.title,
                media.path,
                playlog.started
            FROM playlog
            LEFT JOIN media ON playlog.media_id = media.id
            ORDER BY playlog.started DESC
            LIMIT 10
            """)
        ).fetchall()

        recent_played = [dict(row._mapping) for row in recent_played]

    return {
        "total_clips": total,
        "blocked_clips": blocked,
        "clips_per_category": category_counts,
        "recent_played_clips": recent_played
    }
