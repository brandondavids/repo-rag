from __future__ import annotations
import os
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv

@dataclass(frozen=True)
class Settings:
    discord_token: str
    discord_owner_id: int
    gemini_api_key: str
    discord_guild_id: int | None
    docs_source_dir: Path
    chroma_dir: Path
    chroma_collection: str
    embedding_model: str
    gemini_model: str
    news_channel_id: int | None
    news_timezone: str
    news_digest_time: str
    news_lookback_hours: int
    news_max_items_per_category: int
    tech_news_feeds: list[str]
    anime_manga_news_feeds: list[str]

def _optional_int(value: str | None) -> int | None:
    if value is None or value.strip() == "":
        return None
    return int(value)

def _feed_list(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(";") if item.strip()]

def load_settings() -> Settings:
    load_dotenv()

    required = {
        "DISCORD_TOKEN": os.getenv("DISCORD_TOKEN"),
        "DISCORD_OWNER_ID": os.getenv("DISCORD_OWNER_ID"),
        "GEMINI_API_KEY": os.getenv("GEMINI_API_KEY"),
    }

    missing = [key for key, value in required.items() if not value]
    if missing:
        raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")
    
    return Settings(
        discord_token=required["DISCORD_TOKEN"] or "",
        discord_owner_id=int(required["DISCORD_OWNER_ID"] or "0"),
        gemini_api_key=required["GEMINI_API_KEY"] or "",
        discord_guild_id=_optional_int(os.getenv("DISCORD_GUILD_ID")),
        docs_source_dir=Path(os.getenv("DOCS_SOURCE_DIR", "docs_source")),
        chroma_dir=Path(os.getenv("CHROMA_DIR", "knowledge_db")),
        chroma_collection=os.getenv("CHROMA_COLLECTION", "personal_kb"),
        embedding_model=os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"),
        gemini_model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
        news_channel_id=_optional_int(os.getenv("NEWS_CHANNEL_ID")),
        news_timezone=os.getenv("NEWS_TIMEZONE", "Asia/Jakarta"),
        news_digest_time=os.getenv("NEWS_DIGEST_TIME", "08:00"),
        news_lookback_hours=int(os.getenv("NEWS_LOOKBACK_HOURS", "24")),
        news_max_items_per_category=int(os.getenv("NEWS_MAX_ITEMS_PER_CATEGORY", "8")),
        tech_news_feeds=_feed_list(os.getenv("TECH_NEWS_FEEDS")),
        anime_manga_news_feeds=_feed_list(os.getenv("ANIME_MANGA_NEWS_FEEDS")),
    )