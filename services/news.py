from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from html import unescape

import feedparser
from bs4 import BeautifulSoup

@dataclass(frozen=True)
class NewsItem:
    category: str
    title: str
    url: str
    source: str
    published_at: datetime
    summary: str

class NewsDigestService:
    def __init__(
        self,
        categories: dict[str, list[str]],
        lookback_hours: int = 24,
        max_items_per_category: int = 8,
    ) -> None:
        self.categories = categories
        self.lookback_hours = lookback_hours
        self.max_items_per_category = max_items_per_category

    def build_digest(self, now: datetime | None = None) -> str:
        now = now or datetime.now(timezone.utc)
        cutoff = now - timedelta(hours=self.lookback_hours)

        sections: list[str] = [
            f"Daily news digest from the past {self.lookback_hours} hours",
            f"Window: {cutoff:%d-%m-%Y %H:%M UTC} to {now:%d-%m-%Y %H:%M UTC}",
        ]

        for category, feed_urls in self.categories.items():
            items = self._collect_category(category, feed_urls, cutoff, now)
            sections.append(self._format_category(category, items))

        return "\n\n".join(sections)
    
    def _collect_category(
        self,
        category: str,
        feed_urls: list[str],
        cutoff: datetime,
        now: datetime,
    ) -> list[NewsItem]:
        seen: set[str] = set()
        items: list[NewsItem] = []

        for feed_url in feed_urls:
            parsed = feedparser.parse(feed_url)
            feed_title = parsed.feed.get("title") or feed_url

            for entry in parsed.entries:
                source = str(
                    entry.get("source", {}).get("title")
                    or feed_title
                )
                title = self._clean_text(str(entry.get("title", "")))
                url = str(entry.get("link", "")).strip()
                published_at = self._entry_datetime(entry)

                if not title or not url or published_at is None:
                    continue
                if published_at < cutoff or published_at > now + timedelta(hours=1):
                    continue

                dedupe_key = url.lower() or title.lower()
                if dedupe_key in seen:
                    continue
                seen.add(dedupe_key)

                summary = self._clean_text(
                    str(entry.get("summary") or entry.get("description") or "")
                )
                items.append(
                    NewsItem(
                        category=category,
                        title=title,
                        url=url,
                        source=source,
                        published_at=published_at,
                        summary=summary,
                    )
                )

        items.sort(key=lambda item:item.published_at, reverse=True)
        return items[: self.max_items_per_category]
    
    def _format_category(self, category: str, items: list[NewsItem]) -> str:
        if not items:
            return f"## {category}\nNo recent items found from configured feeds."
        
        lines = [f"## {category}"]
        for index, item in enumerate(items, start=1):
            summary = f"\n  {item.summary[:220]}" if item.summary else ""
            lines.append(
                f"{index}. [{item.title}]({item.url})\n"
                f"  Source: {item.source} | Published: {item.published_at:%d-%m-%Y %H:%M UTC}"
                f"{summary}"
            )
        return "\n\n".join(lines)
        
    @staticmethod
    def _entry_datetime(entry: object) -> datetime | None:
        published = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
        if published is None:
            return None
        timestamp = calendar.timegm(published)
        return datetime.fromtimestamp(timestamp, timezone.utc)
    
    @staticmethod
    def _clean_text(text: str) -> str:
        if not text:
            return ""
        stripped = BeautifulSoup(unescape(text), "html.parser").get_text(" ", strip=True)
        return " ".join(stripped.split())