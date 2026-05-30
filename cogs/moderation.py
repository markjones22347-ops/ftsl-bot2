"""
FTSL Bot — Moderation cog
Commands: /warn, /warnings, /clearwarnings, /announce, /embed, /say
"""

import discord
from discord import app_commands, ui
from discord.ext import commands
import json
import os
from datetime import datetime, timezone

LOGS_CHANNEL_ID = 1510346572561383454
FOUNDER_ROLE_ID = 1500217835950047323
SUPPORT_ROLE_ID = 1500217897166049351

# ─── Persistent warning store (flat JSON file) ───────────────────────────────
WARNINGS_FILE = "warnings.json"


def _load_warnings() -> dict:
    if os.path.exists(WARNINGS_FILE):
        with open(WARNINGS_FILE, "r") as f:
            return json.load(f)
    return {}


def _save_warnings(data: dict):
    with open(WARNINGS_FILE, "w") as f:
        json.dump(data, f, indent=2)


def _add_warning(guild_id: int, user_id: int, reason: str, moderator: str) -> int:
    data = _load_warnings()
    key  = str(guild_id)
    if key not in data:
        data[key] = {}
    uid = str(user_id)
    if uid not in data[key]:
        data[key][uid] = []
    data[key][uid].append({
        "reason":    reason,
        "moderator": moderator,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    _save_warnings(data)
    return len(data[key][uid])


def _get_warnings(guild_id: int, user_id: int) -> list:
    data = _load_warnings()
    return data.get(str(guild_id), {}).get(str(user_id), [])


def _clear_warnings(guild_id: int, user_id: int):
    data = _load_warnings()
    key  = str(guild_id)
    if key in data and str(user_id) in data[key]:
        del data[key][str(user_id)]
        _save_warnings(data)


def is_staff(member: discord.Member) -> bool:
    role_ids = {r.id for r in member.roles}
    return FOUNDER_ROLE_ID in role_ids or SUPPORT_ROLE_ID in role_ids


# ══════════════════════════════════════════════════════════════════════════════
#  Announce modal
# ══════════════════════════════════════════════════════════════════════════════

class AnnounceModal(ui.Modal, title="Send Announcement"):
    ann_title = ui.TextInput(
        label="Title",
        placeholder="Announcement title",
        style=discord.TextStyle.short,
        max_length=200,
    )
    ann_body = ui.TextInput(
        label="Message",
        placeholder="Write your announcement here...",
        style=discord.TextStyle.paragraph,
        max_length=2000,
    )

    def __init__(self, channel: discord.TextChannel):
        super().__init__()
        self.target_channel = channel

    async def on_submit(self, interaction: discord.Interaction):
        view = ui.LayoutView()
        view.add_item(ui.Container(
            ui.TextDisplay(f"## {self.ann_title.value}"),
            ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
            ui.TextDisplay(self.ann_body.value),
            ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
            ui.TextDisplay(f"-# Announced by {interaction.user.display_name}"),
        ))
        await self.target_channel.send(view=view)
        await interaction.response.send_message(
            f"Announcement sent to {self.target_channel.mention}.", ephemeral=True
        )


# ══════════════════════════════════════════════════════════════════════════════
#  Embed modal
# ══════════════════════════════════════════════════════════════════════════════

class EmbedModal(ui.Modal, title="Send Embed"):
    emb_title = ui.TextInput(
        label="Title",
        placeholder="Embed title",
        style=discord.TextStyle.short,
        max_length=256,
    )
    emb_description = ui.TextInput(
        label="Description",
        placeholder="Embed body text",
        style=discord.TextStyle.paragraph,
        max_length=2000,
    )
    emb_color = ui.TextInput(
        label="Colour (hex, optional)",
        placeholder="#5865F2",
        style=discord.TextStyle.short,
        max_length=7,
        required=False,
    )

    def __init__(self, channel: discord.TextChannel):
        super().__init__()
        self.target_channel = channel

    async def on_submit(self, interaction: discord.Interaction):
        colour = discord.Colour.blurple()
        if self.emb_color.value:
            try:
                colour = discord.Colour.from_str(self.emb_color.value)
            except ValueError:
                pass

        embed = discord.Embed(
            title=self.emb_title.value,
            description=self.emb_description.value,
            colour=colour,
            timestamp=datetime.now(timezone.utc),
        )
        embed.set_footer(text=f"Sent by {interaction.user.display_name}")
        await self.target_channel.send(embed=embed)
        await interaction.response.send_message(
            f"Embed sent to {self.target_channel.mention}.", ephemeral=True
        )


# ══════════════════════════════════════════════════════════════════════════════
#  Cog
# ══════════════════════════════════════════════════════════════════════════════

class ModerationCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _log(self, guild: discord.Guild, embed: discord.Embed):
        ch = guild.get_channel(LOGS_CHANNEL_ID)
        if ch:
            await ch.send(embed=embed)

    # ── /warn ─────────────────────────────────────────────────────────────────
    @app_commands.command(name="warn", description="Warn a member.")
    @app_commands.describe(member="Member to warn", reason="Reason for the warning")
    async def warn(self, interaction: discord.Interaction, member: discord.Member, reason: str):
        if not is_staff(interaction.user):
            await interaction.response.send_message("You don't have permission to warn members.", ephemeral=True)
            return
        if member.bot:
            await interaction.response.send_message("You can't warn a bot.", ephemeral=True)
            return

        count = _add_warning(interaction.guild.id, member.id, reason, str(interaction.user))

        # Notify the warned user
        try:
            await member.send(
                f"You have been warned in **{interaction.guild.name}**.\n"
                f"**Reason:** {reason}\n"
                f"This is warning **#{count}** on your account."
            )
        except discord.Forbidden:
            pass

        await interaction.response.send_message(
            f"{member.mention} has been warned. They now have **{count}** warning(s)."
        )

        embed = discord.Embed(title="Member Warned", colour=discord.Colour.orange(),
                              timestamp=datetime.now(timezone.utc))
        embed.add_field(name="Member",    value=f"{member} ({member.id})", inline=False)
        embed.add_field(name="Reason",    value=reason,                    inline=False)
        embed.add_field(name="Moderator", value=str(interaction.user),     inline=False)
        embed.add_field(name="Total Warnings", value=str(count),           inline=False)
        await self._log(interaction.guild, embed)

    # ── /warnings ────────────────────────────────────────────────────────────
    @app_commands.command(name="warnings", description="View warnings for a member.")
    @app_commands.describe(member="Member to check")
    async def warnings(self, interaction: discord.Interaction, member: discord.Member):
        if not is_staff(interaction.user):
            await interaction.response.send_message("You don't have permission to view warnings.", ephemeral=True)
            return

        warns = _get_warnings(interaction.guild.id, member.id)
        if not warns:
            await interaction.response.send_message(f"{member.mention} has no warnings.", ephemeral=True)
            return

        embed = discord.Embed(
            title=f"Warnings — {member.display_name}",
            description=f"{len(warns)} warning(s) on record.",
            colour=discord.Colour.orange(),
        )
        for i, w in enumerate(warns, 1):
            ts = w["timestamp"][:10]
            embed.add_field(
                name=f"#{i} — {ts}",
                value=f"**Reason:** {w['reason']}\n**By:** {w['moderator']}",
                inline=False,
            )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ── /clearwarnings ───────────────────────────────────────────────────────
    @app_commands.command(name="clearwarnings", description="Clear all warnings for a member (Founder only).")
    @app_commands.describe(member="Member to clear warnings for")
    async def clearwarnings(self, interaction: discord.Interaction, member: discord.Member):
        founder_role = interaction.guild.get_role(FOUNDER_ROLE_ID)
        if founder_role not in interaction.user.roles:
            await interaction.response.send_message("Only the Founder role can clear warnings.", ephemeral=True)
            return
        _clear_warnings(interaction.guild.id, member.id)
        await interaction.response.send_message(f"All warnings cleared for {member.mention}.")

        embed = discord.Embed(title="Warnings Cleared", colour=discord.Colour.green(),
                              timestamp=datetime.now(timezone.utc))
        embed.add_field(name="Member",    value=f"{member} ({member.id})", inline=False)
        embed.add_field(name="Cleared by", value=str(interaction.user),   inline=False)
        await self._log(interaction.guild, embed)

    # ── /announce ────────────────────────────────────────────────────────────
    @app_commands.command(name="announce", description="Send a formatted announcement to a channel.")
    @app_commands.describe(channel="Channel to send the announcement to")
    async def announce(self, interaction: discord.Interaction, channel: discord.TextChannel):
        if not is_staff(interaction.user):
            await interaction.response.send_message("You don't have permission to send announcements.", ephemeral=True)
            return
        await interaction.response.send_modal(AnnounceModal(channel))

    # ── /embed ───────────────────────────────────────────────────────────────
    @app_commands.command(name="embed", description="Send a custom embed to a channel.")
    @app_commands.describe(channel="Channel to send the embed to")
    async def embed_cmd(self, interaction: discord.Interaction, channel: discord.TextChannel):
        if not is_staff(interaction.user):
            await interaction.response.send_message("You don't have permission to send embeds.", ephemeral=True)
            return
        await interaction.response.send_modal(EmbedModal(channel))

    # ── /say ─────────────────────────────────────────────────────────────────
    @app_commands.command(name="say", description="Have the bot send a message in a channel.")
    @app_commands.describe(channel="Channel to send to", message="Message content")
    async def say(self, interaction: discord.Interaction, channel: discord.TextChannel, message: str):
        if not is_staff(interaction.user):
            await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
            return
        await channel.send(message)
        await interaction.response.send_message(f"Message sent to {channel.mention}.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(ModerationCog(bot))
