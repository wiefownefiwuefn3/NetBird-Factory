# discord_bot.py – runs on the admin runner, uses localhost API
import os
import asyncio
import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

DISCORD_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
GUILD_ID = int(os.getenv("DISCORD_GUILD_ID", 0))

if not DISCORD_TOKEN or not GUILD_ID:
    raise ValueError("Missing environment variables")

BASE_URL = "http://localhost:5000"

class AdminClient:
    def __init__(self, session):
        self.session = session

    async def get_workers(self):
        try:
            async with self.session.get(f"{BASE_URL}/api/workers") as resp:
                if resp.status == 200:
                    return await resp.json()
        except Exception:
            pass
        return []

    async def get_tasks(self):
        try:
            async with self.session.get(f"{BASE_URL}/api/tasks") as resp:
                if resp.status == 200:
                    return await resp.json()
        except Exception:
            pass
        return []

    async def get_results(self, limit=10):
        try:
            async with self.session.get(f"{BASE_URL}/api/results") as resp:
                if resp.status == 200:
                    results = await resp.json()
                    return results[-limit:]
        except Exception:
            pass
        return []

    async def add_task(self, command):
        payload = {"command": command}
        try:
            async with self.session.post(f"{BASE_URL}/api/tasks", json=payload) as resp:
                return resp.status == 200
        except Exception:
            return False

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True

class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)
        self.admin = None
        self.http_session = None

    async def setup_hook(self):
        self.http_session = aiohttp.ClientSession()
        self.admin = AdminClient(self.http_session)
        guild = discord.Object(id=GUILD_ID)
        self.tree.copy_global_to(guild=guild)
        await self.tree.sync(guild=guild)
        print("Bot synced")

    async def close(self):
        if self.http_session:
            await self.http_session.close()
        await super().close()

bot = MyBot()

@bot.tree.command(name="workers", description="List all connected workers")
async def workers(interaction: discord.Interaction):
    await interaction.response.defer()
    workers = await bot.admin.get_workers()
    if not workers:
        await interaction.followup.send("No workers found.")
        return
    embed = discord.Embed(title=f"Workers ({len(workers)})", color=0x00ff00)
    for w in workers:
        name = w.get("hostname", w.get("ip", "Unknown"))
        ip = w.get("ip", "?")
        os = w.get("os", "?")
        last = w.get("lastSeen", "?")
        embed.add_field(name=name, value=f"IP: {ip}\nOS: {os}\nLast seen: {last}", inline=False)
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="run", description="Execute a command on all workers")
async def run(interaction: discord.Interaction, command: str):
    await interaction.response.defer(ephemeral=True)
    success = await bot.admin.add_task(command)
    if success:
        await interaction.followup.send(f"✅ Task `{command}` queued.", ephemeral=True)
    else:
        await interaction.followup.send("❌ Failed to queue task. Is the admin API reachable?", ephemeral=True)

@bot.tree.command(name="tasks", description="Show pending tasks")
async def tasks(interaction: discord.Interaction):
    await interaction.response.defer()
    tasks = await bot.admin.get_tasks()
    if not tasks:
        await interaction.followup.send("No pending tasks.")
        return
    embed = discord.Embed(title=f"Pending Tasks ({len(tasks)})", color=0xffaa00)
    for t in tasks:
        embed.add_field(name=f"Task {t.get('id')}", value=t.get('command'), inline=False)
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="results", description="Show recent results")
async def results(interaction: discord.Interaction):
    await interaction.response.defer()
    results = await bot.admin.get_results(limit=10)
    if not results:
        await interaction.followup.send("No results yet.")
        return
    embed = discord.Embed(title="Recent Results", color=0x00ccff)
    for r in results:
        worker = r.get('worker', '?')
        output = r.get('output', '')[:200]
        embed.add_field(name=f"Task {r.get('taskId')} – {worker}", value=output, inline=False)
    await interaction.followup.send(embed=embed)

if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)
