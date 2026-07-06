from __future__ import annotations

import asyncio

import discord
from discord import app_commands
from discord.ext import commands

MAX_DISCORD_MESSAGE = 1900

def is_owner_allowed(
    interaction: discord.Interaction,
    owner_id: int,
    test_guild_id: int | None,
) -> tuple[bool, str | None]:
    if interaction.user.id != owner_id:
        return False, "Access denied, this bot is owner-only!"
    if interaction.guild is None:
        return True, None
    if test_guild_id and interaction.guild_id == test_guild_id:
        return True, None
    return False, "Use this command in a DM with the bot."

async def _send_long(interaction: discord.Interaction, text: str, ephemeral: bool) -> None:
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
    for chunk in chunks or ["No output."]:
        await interaction.followup.send(chunk, ephemeral=ephemeral)

class RagCommands(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="ask", description="Ask a question using your private knowledge base.")
    @app_commands.describe(query="The question to answer from your indexed documents.")
    async def ask(self, interaction: discord.Interaction, query: str) -> None:
        allowed, reason = is_owner_allowed(
            interaction,
            self.bot.settings.discord_owner_id,
            self.bot.settings.discord_guild_id,
        )
        if not allowed:
            await interaction.response.send_message(reason, ephemeral=True)
            return
        
        ephemeral = interaction.guild is not None
        await interaction.response.defer(thinking=True, ephemeral=ephemeral)
        answer = await asyncio.to_thread(self.bot.rag_engine.ask, query, 5)
        await _send_long(interaction, answer, ephemeral=ephemeral)

    @app_commands.command(name="search", description="Search something from your knowledge base.")
    @app_commands.describe(query="The search query.")
    async def search(self, interaction: discord.Interaction, query: str) -> None:
        allowed, reason = is_owner_allowed(
            interaction,
            self.bot.settings.discord_owner_id,
            self.bot.settings.discord_guild_id,
        )
        if not allowed:
            await interaction.response.send_message(reason, ephemeral=True)
            return

        ephemeral = interaction.guild is not None
        await interaction.response.defer(thinking=True, ephemeral=ephemeral)
        results = await asyncio.to_thread(self.bot.rag_engine.retrieve, query, 5)
        if not results:
            await interaction.followup.send("No matches found.", ephemeral=ephemeral)
            return
        
        lines: list[str] = []
        for index, result in enumerate(results, start=1):
            metadata = result["metadata"] if isinstance(result["metadata"], dict) else {}
            source = metadata.get("source", "unknown")
            page = metadata.get("page")
            distance = result.get("distance", 0.0)
            label = f"{source} p. {page}" if page else str (source)
            snippet = str(result["document"]).replace("\n", " ")[:500]
            lines.append(f"**{index}. {label}** | distance `{distance:.4f}`\n{snippet}")

        await _send_long(interaction, "\n\n".join(lines), ephemeral=ephemeral)

    @app_commands.command(name="ingest", description="Ingest new or changed files in docs source.")
    async def ingest(self, interaction: discord.Interaction) -> None:
        allowed, reason = is_owner_allowed(
            interaction,
            self.bot.settings.discord_owner_id,
            self.bot.settings.discord_guild_id,
        )
        if not allowed:
            await interaction.response.send_message(reason, ephemeral=True)
            return
        
        ephemeral = interaction.guild is not None
        await interaction.response.defer(thinking=True, ephemeral=ephemeral)
        results = await asyncio.to_thread(self.bot.ingestion_manager.ingest_directory)
        if not results:
            await interaction.followup.send("No supported files found.", ephemeral=ephemeral)
            return
        
        added = sum(result.chunks_added for result in results)
        changed = [result for result in results if result.status != "unchanged"]
        await interaction.followup.send(
            f"Checked {len(results)} file(s). Indexed {len(changed)} changed file(s). Added {added} chunk(s).",
            ephemeral=ephemeral,
        )

    @app_commands.command(name="kb_status", description="Show knowledge-base diagnostics.")
    async def kb_status(self, interaction: discord.Interaction) -> None:
        allowed, reason = is_owner_allowed(
            interaction,
            self.bot.settings.discord_owner_id,
            self.bot.settings.discord_guild_id,
        )
        if not allowed:
            await interaction.response.send_message(reason, ephemeral=True)
            return
        
        status = await asyncio.to_thread(self.bot.ingestion_manager.status)
        files = status["files"]
        preview = "\n".join(f"-{path}" for path in files[:10])
        if len(files) > 10:
            preview += f"\n- ...and {len(files) - 10} more"

        await interaction.response.send_message(
            f"Indexed files: `{status['indexed_files']}`\n"
            f"Chunks: `{status['chunks']}`\n"
            f"{preview or 'No files indexed yet.'}",
            ephemeral=interaction.guild is not None,
        )

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(RagCommands(bot))