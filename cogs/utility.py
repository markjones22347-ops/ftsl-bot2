"""
FTSL Bot — Utility cog
Commands: /userinfo, /serverinfo
"""

import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime, timezone


def _format_dt(dt: datetime) -> str:
    return f"<t:{int(dt.timestamp())}:F> (<t:{int(dt.timestamp())}:R>)"


class UtilityCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ── /userinfo ─────────────────────────────────────────────────────────────
    @app_commands.command(name="userinfo", description="Show information about a member.")
    @app_commands.describe(member="Member to look up (defaults to yourself)")
    async def userinfo(self, interaction: discord.Interaction, member: discord.Member = None):
        member = member or interaction.user

        roles = [r.mention for r in reversed(member.roles) if r != interaction.guild.default_role]
        roles_str = " ".join(roles) if roles else "None"

        embed = discord.Embed(
            title=f"{member.display_name}",
            colour=member.colour if member.colour.value else discord.Colour.blurple(),
            timestamp=datetime.now(timezone.utc),
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="Username",     value=str(member),              inline=True)
        embed.add_field(name="ID",           value=str(member.id),           inline=True)
        embed.add_field(name="Bot",          value="Yes" if member.bot else "No", inline=True)
        embed.add_field(name="Account Created", value=_format_dt(member.created_at), inline=False)
        embed.add_field(name="Joined Server",   value=_format_dt(member.joined_at) if member.joined_at else "Unknown", inline=False)
        embed.add_field(name=f"Roles ({len(roles)})", value=roles_str[:1024], inline=False)

        if member.premium_since:
            embed.add_field(name="Boosting Since", value=_format_dt(member.premium_since), inline=False)

        embed.set_footer(text=f"Requested by {interaction.user.display_name}")
        await interaction.response.send_message(embed=embed)

    # ── /serverinfo ───────────────────────────────────────────────────────────
    @app_commands.command(name="serverinfo", description="Show information about this server.")
    async def serverinfo(self, interaction: discord.Interaction):
        guild = interaction.guild

        # Count channels by type
        text_channels     = len(guild.text_channels)
        voice_channels    = len(guild.voice_channels)
        category_channels = len(guild.categories)

        # Boost info
        boost_level = guild.premium_tier
        boost_count = guild.premium_subscription_count or 0

        # Online members (requires members intent)
        total   = guild.member_count
        bots    = sum(1 for m in guild.members if m.bot)
        humans  = total - bots

        embed = discord.Embed(
            title=guild.name,
            colour=discord.Colour.blurple(),
            timestamp=datetime.now(timezone.utc),
        )
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)

        embed.add_field(name="Owner",       value=guild.owner.mention if guild.owner else "Unknown", inline=True)
        embed.add_field(name="Server ID",   value=str(guild.id),   inline=True)
        embed.add_field(name="Created",     value=_format_dt(guild.created_at), inline=False)
        embed.add_field(name="Members",     value=f"{total} total — {humans} humans, {bots} bots", inline=False)
        embed.add_field(name="Channels",    value=f"{text_channels} text · {voice_channels} voice · {category_channels} categories", inline=False)
        embed.add_field(name="Roles",       value=str(len(guild.roles)), inline=True)
        embed.add_field(name="Emojis",      value=str(len(guild.emojis)), inline=True)
        embed.add_field(name="Boost Level", value=f"Level {boost_level} ({boost_count} boosts)", inline=True)

        if guild.description:
            embed.add_field(name="Description", value=guild.description, inline=False)

        if guild.banner:
            embed.set_image(url=guild.banner.url)

        embed.set_footer(text=f"Requested by {interaction.user.display_name}")
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(UtilityCog(bot))
