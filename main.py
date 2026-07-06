from __future__ import annotations

import asyncio

import discord
from discord.ext import commands

from config import Settings, load_settings
from database.vector_store import VectorStore
from services.embeddings import LocalEmbeddingService
from services.ingestion import IngestionManager
from services.news import NewsDigestService
from services.rag_engine import RagEngine
from services.splitter import RecursiveTextSplitter

class RepoBot(commands.Bot):
    def __init__(self, settings: Settings) -> None:
        intents = discord.Intents.default()
        intents.dm_messages = True
        intents.message_content = False

        super().__init__(command_prefix="r!", intents=intents)
        self.settings = settings

        self.embedding_service = LocalEmbeddingService(settings.embedding_model)
        self.vector_store = VectorStore(settings.chroma_dir, settings.chroma_collection)
        self.ingestion_manager = IngestionManager(
            docs_source_dir=settings.docs_source_dir,
            manifest_path=settings.chroma_dir / "index_manifest.json",
            vector_store=self.vector_store,
            embedding_service=self.embedding_service,
            splitter=RecursiveTextSplitter(chunk_size=900, chunk_overlap=150),
        )
        self.rag_engine = RagEngine(
            vector_store=self.vector_store,
            embedding_service=self.embedding_service,
            gemini_api_key=settings.gemini_api_key,
            model_name=settings.gemini_model,
        )
        self.news_digest_service = NewsDigestService(
            categories={
                "Tech": settings.tech_news_feeds,
                "Anime and Manga": settings.anime_manga_news_feeds,
            },
            lookback_hours=settings.news_lookback_hours,
            max_items_per_category=settings.news_max_items_per_category,
        )

    async def setup_hook(self) -> None:
        await self.load_extension("cogs.news_digest")
        await self.load_extension("cogs.rag_commands")
        await self.load_extension("cogs.uploader")

        if self.settings.discord_guild_id:
            guild = discord.Object(id=self.settings.discord_guild_id)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            print(f"Synced slash commands to server {self.settings.discord_guild_id}")
        else:
            await self.tree.sync()
            print("Synced global slash commands. Global command updates take time to appear.")

    async def on_ready(self) -> None:
        print(f"Logged in!")


async def main() -> None:
    settings = load_settings()
    settings.docs_source_dir.mkdir(parents=True, exist_ok=True)
    settings.chroma_dir.mkdir(parents=True, exist_ok=True)

    bot = RepoBot(settings)
    async with bot:
        await bot.start(settings.discord_token)

if __name__ == "__main__":
    asyncio.run(main())