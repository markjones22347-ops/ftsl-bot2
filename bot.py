import discord
from discord.ext import commands
import os
import sys
from dotenv import load_dotenv
from keep_alive import keep_alive

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")

if not TOKEN:
    print("[FATAL] DISCORD_TOKEN environment variable is not set. Add it in Render → Environment.", flush=True)
    sys.exit(1)

keep_alive()  # Start the HTTP ping server before the bot connects

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    print(f"[FTSL Bot] Logged in as {bot.user} ({bot.user.id})", flush=True)
    try:
        synced = await bot.tree.sync()
        print(f"[FTSL Bot] Synced {len(synced)} slash command(s).", flush=True)
    except Exception as e:
        print(f"[FTSL Bot] Failed to sync commands: {e}", flush=True)


async def main():
    async with bot:
        await bot.load_extension("cogs.tickets")
        await bot.start(TOKEN)


if __name__ == "__main__":
    import asyncio
    try:
        asyncio.run(main())
    except discord.LoginFailure:
        print("[FATAL] Invalid Discord token. Check your DISCORD_TOKEN in Render → Environment.", flush=True)
        sys.exit(1)
    except Exception as e:
        print(f"[FATAL] Unexpected error: {e}", flush=True)
        sys.exit(1)
