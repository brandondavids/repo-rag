from __future__ import annotations

import asyncio
import re
from pathlib import Path

import discord
from discord.ext import commands

from services.loaders import SUPPORTED_EXTENSIONS

def _safe_filename(filename: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", filename).strip("._")
    return cleaned or "upload"

class Uploader(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.upload_dir = self.bot.settings.docs_source_dir / "uploads"
        self.upload_dir.mkdir(parents=True, exist_ok=True)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot:
            return
        if message.guild is not None:
            return
        if message.author.id != self.bot.settings.discord_owner_id:
            await message.reply("Access denied, this bot is owner-only!", mention_author=False)
            return
        if not message.attachments:
            return
        
        indexed = 0
        skipped: list[str] = []

        for attachment in message.attachments:
            suffix = Path(attachment.filename).suffix.lower()
            if suffix not in SUPPORTED_EXTENSIONS:
                skipped.append(attachment.filename)
                continue

            destination = self.upload_dir / _safe_filename(attachment.filename)
            await attachment.save(destination)
            result = await asyncio.to_thread(self.bot.ingestion_manager.ingest_file, destination)
            indexed += result.chunks_added

        response = f"Ingested uploaded files. Added {indexed} chunk(s)."
        if skipped:
            response += f"\nSkipped unsupported file(s): {','.join(skipped)}"
        await message.reply(response, mention_author=False)

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Uploader(bot))