from __future__ import annotations

import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo

import discord
from discord import app_commands
from discord.ext import commands, tasks

MAX_DISCORD_MESSAGE = 1900

def _parse_digest_time(value: str) -> tuple[int, int]:
    hour_text, minute_text = value.split(":", maxsplit=1)
    hour = int(hour_text)
    minute = int(minute_text)
    if not 0 <= hour <= 23 or not 0 <= minute <= 59:
        raise ValueError("NEWS_DIGEST_TIME must use HH:MM in 24-hour time")
    return hour, minute

async def _send_long(destination: discord.abc.Messageable, text: str) -> None:
    chunks: list[str] = []
    current = ""
    for block in text.split("\n\n"):
        candidate = f"{current}\n\n{block}" if current else block
        if len(candidate) <= MAX_DISCORD_MESSAGE:
            current = candidate
        else:
            if current:
                chunks.append(current)
            current = block
    if current:
        chunks.append(current)
    for chunk in chunks or ["No news digest output."]:
        await destination.send(chunk)

class NewsDigest(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.timezone = ZoneInfo(self.bot.settings.news_timezone)
        self.target_hour, self.target_minute = _parse_digest_time(
            self.bot.settings.news_digest_time
        )
        self.last_sent_date: str | None = None
        self.daily_digest.start()
    
    def cog_unload(self) -> None:
        self.daily_digest.cancel()

    @tasks.loop(minutes=1)
    async def daily_digest(self) -> None:
        if not self.bot.settings.news_channel_id:
            return
        
        now = datetime.now(self.timezone)
        today = now.date().isoformat()
        current_minutes = now.hour * 60 + now.minute
        target_minutes = self.target_hour * 60 + self.target_minute

        if current_minutes < target_minutes or self.last_sent_date == today:
            return
        
        channel = self.bot.get_channel(self.bot.settings.news_channel_id)
        if channel is None:
            channel = await self.bot.fetch_channel(self.bot.settings.news_channel_id)

        digest = await asyncio.to_thread(self.bot.news_digest_service.build_digest)
        await _send_long(channel, digest)
        self.last_sent_date = today

    @daily_digest.before_loop
    async def before_daily_digest(self) -> None:
        await self.bot.wait_until_ready()

    @app_commands.command(name="news_now", description="Send the latest configured news digest now.")
    async def news_now(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.bot.settings.discord_owner_id:
            await interaction.response.send_message("Access denied, this bot is owner-only!", ephemeral=True)
            return
        
        await interaction.response.defer(thinking=True, ephemeral=interaction.guild is not None)
        digest = await asyncio.to_thread(self.bot.news_digest_service.build_digest)

        if interaction.channel is None:
            await interaction.followup.send("No channel is available for this interaction.", ephemeral=True)
            return
        
        chunks = [digest[i : i + MAX_DISCORD_MESSAGE] for i in range(0, len(digest), MAX_DISCORD_MESSAGE)]
        for chunk in chunks or ["No news digest output."]:
            await interaction.followup.send(chunk, ephemeral=interaction.guild is not None)

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(NewsDigest(bot))