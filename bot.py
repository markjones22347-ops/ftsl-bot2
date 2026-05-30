import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
from keep_alive import keep_alive

load_dotenv()

keep_alive()  # Start the HTTP ping server before the bot connects

TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    print(f"[FTSL Bot] Logged in as {bot.user} ({bot.user.id})")
    try:
        synced = await bot.tree.sync()
        print(f"[FTSL Bot] Synced {len(synced)} slash command(s).")
    except Exception as e:
        print(f"[FTSL Bot] Failed to sync commands: {e}")


async def main():
    async with bot:
        await bot.load_extension("cogs.tickets")
        await bot.start(TOKEN)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
