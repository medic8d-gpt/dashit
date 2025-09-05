from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ArticleBase(BaseModel):
    source: Optional[str] = None
    url: Optional[str] = None
    headline: Optional[str] = None
    summary: Optional[str] = None
    published: Optional[str] = Field(
        default=None,
        description="ISO datetime string; stored as TEXT in SQLite",
    )
    posted: Optional[int] = Field(default=None, ge=0, le=1)


class ArticleCreate(BaseModel):
    source: str
    url: str
    headline: str
    summary: Optional[str] = None
    published: Optional[str] = None
    posted: Optional[int] = Field(default=0, ge=0, le=1)


class ArticleUpdate(ArticleBase):
    pass


class ArticleOut(BaseModel):
    id: int
    hash: Optional[str] = None
    source: str
    url: str
    headline: str
    summary: Optional[str] = None
    published: Optional[str] = None
    posted: int

    class Config:
        from_attributes = True


class StatsOut(BaseModel):
    total: int
    posted: int
    unposted: int
    by_source: dict[str, int]

