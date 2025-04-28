from pydantic import BaseModel
from typing import Optional

class Media(BaseModel):
    id: int
    path: str
    artist: Optional[str]
    title: Optional[str]
    release_year: Optional[int]
    description: Optional[str]
    type: Optional[str]
    blocked: Optional[int]
    duration: Optional[float]
    category: Optional[str] = None

    class Config:
        orm_mode = True


class MediaUpdate(BaseModel):
    artist: Optional[str] = None
    title: Optional[str] = None
    release_year: Optional[int] = None
    description: Optional[str] = None
    blocked: Optional[int] = None
    category: Optional[str] = None


class DashboardStats(BaseModel):
    total_clips: int
    blocked_clips: int
    clips_per_category: dict
    recent_played_clips: list
