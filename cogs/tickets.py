"""
FTSL Bot — Ticket System (discord.py 2.6+)
Features: purchase/support tickets, transcripts, priority flag, add/remove user.
"""

import discord
from discord import app_commands, ui
from discord.ext import commands
import asyncio
import time
import io
from datetime import datetime, timezone

# ─── Role IDs ────────────────────────────────────────────────────────────────
FOUNDER_ROLE_ID = 1500217835950047323
SUPPORT_ROLE_ID = 1500217897166049351

# ─── Channel IDs ─────────────────────────────────────────────────────────────
LOGS_CHANNEL_ID = 1510346572561383454

# ─── Category names ──────────────────────────────────────────────────────────
PURCHASE_CATEGORY = "Purchase Tickets"
SUPPORT_CATEGORY  = "Support Tickets"

# ─── Remind cooldown (seconds) ───────────────────────────────────────────────
REMIND_COOLDOWN = 3600

# ─── In-memory stores ────────────────────────────────────────────────────────
_remind_cooldowns: dict[int, float] = {}   # channel_id -> last remind timestamp
_ticket_openers:   dict[int, int]   = {}   # channel_id -> opener user_id
_ticket_types:     dict[int, str]   = {}   # channel_id -> "purchase" | "support"


# ══════════════════════════════════════════════════════════════════════════════
#  Helpers
# ══════════════════════════════════════════════════════════════════════════════

async def get_or_create_category(guild: discord.Guild, name: str) -> discord.CategoryChannel:
    cat = discord.utils.get(guild.categories, name=name)
    if cat is None:
        cat = await guild.create_category(name)
    return cat


async def cleanup_empty_categories(guild: discord.Guild):
    for cat_name in (PURCHASE_CATEGORY, SUPPORT_CATEGORY):
        cat = discord.utils.get(guild.categories, name=cat_name)
        if cat and len(cat.channels) == 0:
            await cat.delete(reason="No ticket channels remaining.")


def is_staff(member: discord.Member) -> bool:
    """True if member has Founder or Support role."""
    role_ids = {r.id for r in member.roles}
    return FOUNDER_ROLE_ID in role_ids or SUPPORT_ROLE_ID in role_ids


async def save_transcript(channel: discord.TextChannel, closer: discord.Member) -> io.BytesIO:
    """Collect all messages in the channel and return a plain-text transcript."""
    lines = [
        f"Transcript — #{channel.name}",
        f"Closed by : {closer} ({closer.id})",
        f"Closed at : {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}",
        "=" * 60,
        "",
    ]
    async for msg in channel.history(limit=None, oldest_first=True):
        ts = msg.created_at.strftime("%Y-%m-%d %H:%M:%S")
        content = msg.content or ""
        if msg.embeds:
            content += " [embed]"
        if msg.attachments:
            content += " " + " ".join(a.url for a in msg.attachments)
        lines.append(f"[{ts}] {msg.author} ({msg.author.id}): {content}")

    text = "\n".join(lines)
    return io.BytesIO(text.encode("utf-8"))


async def post_transcript(
    guild: discord.Guild,
    channel: discord.TextChannel,
    closer: discord.Member,
    opener_id: int,
):
    """Send transcript to logs channel and DM the opener."""
    buf = await save_transcript(channel, closer)
    filename = f"transcript-{channel.name}.txt"

    # Post to logs channel
    logs_ch = guild.get_channel(LOGS_CHANNEL_ID)
    if logs_ch:
        embed = discord.Embed(
            title="Ticket Transcript",
            description=(
                f"**Channel:** #{channel.name}\n"
                f"**Closed by:** {closer.mention}\n"
                f"**Time:** <t:{int(datetime.now(timezone.utc).timestamp())}:F>"
            ),
            colour=discord.Colour.blurple(),
        )
        buf.seek(0)
        await logs_ch.send(embed=embed, file=discord.File(buf, filename=filename))

    # DM the opener
    opener = guild.get_member(opener_id)
    if opener:
        try:
            buf.seek(0)
            await opener.send(
                f"Your ticket **#{channel.name}** has been closed. Here's your transcript:",
                file=discord.File(buf, filename=filename),
            )
        except discord.Forbidden:
            pass  # DMs disabled


# ══════════════════════════════════════════════════════════════════════════════
#  Panel builder
# ══════════════════════════════════════════════════════════════════════════════

def build_panel_view() -> ui.LayoutView:
    view = ui.LayoutView()
    view.add_item(ui.Container(
        ui.TextDisplay("## FTSL Ticket System"),
        ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
        ui.TextDisplay(
            "Need help or looking to make a purchase? Open a ticket below and "
            "someone from our team will be with you shortly.\n\n"
            "**Purchase** — Interested in buying something from us? Fill out a short "
            "form with the details and we'll get back to you.\n\n"
            "**Support** — Running into an issue or need assistance? Describe your "
            "situation and a team member will respond as soon as possible."
        ),
        ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
        ui.TextDisplay("-# FTSL Bot — Ticket System"),
    ))
    view.add_item(ui.ActionRow(TicketTypeSelect()))
    return view


# ══════════════════════════════════════════════════════════════════════════════
#  Modals
# ══════════════════════════════════════════════════════════════════════════════

class PurchaseModal(ui.Modal, title="Purchase Request"):
    what_to_buy = ui.TextInput(
        label="What would you like to purchase?",
        placeholder="e.g. Premium subscription, custom bot, etc.",
        style=discord.TextStyle.paragraph,
        max_length=500,
    )
    payment_method = ui.TextInput(
        label="What are you paying with?",
        placeholder="e.g. PayPal, Crypto, LTC, etc.",
        style=discord.TextStyle.short,
        max_length=100,
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        await open_ticket(interaction, "purchase", {
            "what": self.what_to_buy.value,
            "payment": self.payment_method.value,
        })


class SupportModal(ui.Modal, title="Support Request"):
    issue = ui.TextInput(
        label="What is your issue?",
        placeholder="Describe your problem in detail.",
        style=discord.TextStyle.paragraph,
        max_length=1000,
    )
    help_needed = ui.TextInput(
        label="What exactly do you need help with?",
        placeholder="Be as specific as possible.",
        style=discord.TextStyle.paragraph,
        max_length=500,
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        await open_ticket(interaction, "support", {
            "issue": self.issue.value,
            "help_needed": self.help_needed.value,
        })


# ══════════════════════════════════════════════════════════════════════════════
#  Ticket open logic
# ══════════════════════════════════════════════════════════════════════════════

async def open_ticket(interaction: discord.Interaction, ticket_type: str, extra: dict):
    guild  = interaction.guild
    member = interaction.user

    cat_name     = PURCHASE_CATEGORY if ticket_type == "purchase" else SUPPORT_CATEGORY
    channel_name = f"{ticket_type}-{member.name.lower()}"

    category = await get_or_create_category(guild, cat_name)
    existing = discord.utils.get(category.channels, name=channel_name)
    if existing:
        await interaction.followup.send(
            f"You already have an open ticket: {existing.mention}", ephemeral=True
        )
        return

    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        member: discord.PermissionOverwrite(
            view_channel=True, send_messages=True, read_message_history=True
        ),
        guild.me: discord.PermissionOverwrite(
            view_channel=True, send_messages=True,
            manage_channels=True, manage_messages=True
        ),
    }
    founder_role = guild.get_role(FOUNDER_ROLE_ID)
    support_role = guild.get_role(SUPPORT_ROLE_ID)
    if founder_role:
        overwrites[founder_role] = discord.PermissionOverwrite(
            view_channel=True, send_messages=True, read_message_history=True
        )
    if support_role:
        overwrites[support_role] = discord.PermissionOverwrite(
            view_channel=True, send_messages=True, read_message_history=True
        )

    channel = await category.create_text_channel(
        name=channel_name,
        overwrites=overwrites,
        topic=f"Ticket opened by {member} ({member.id}) | Type: {ticket_type}",
    )

    # Register ticket metadata
    _remind_cooldowns[channel.id] = 0
    _ticket_openers[channel.id]   = member.id
    _ticket_types[channel.id]     = ticket_type

    if support_role:
        await channel.send(support_role.mention)

    if ticket_type == "purchase":
        header  = f"## Purchase Ticket — {member.display_name}"
        intro   = "Thanks for reaching out. Someone from our team will be with you shortly.\nHere's a summary of what you submitted:"
        details = f"**Purchase Details**\n```\nItem / Service : {extra['what']}\nPayment Method : {extra['payment']}\n```"
    else:
        header  = f"## Support Ticket — {member.display_name}"
        intro   = "Thanks for opening a ticket. A support member will be with you as soon as possible.\nHere's a summary of what you submitted:"
        details = f"**Issue Details**\n```\nIssue       : {extra['issue']}\nHelp Needed : {extra['help_needed']}\n```"

    view = ui.LayoutView()
    view.add_item(ui.Container(
        ui.TextDisplay(header),
        ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
        ui.TextDisplay(intro),
        ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
        ui.TextDisplay(details),
        ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
        ui.TextDisplay(f"**Opened by:** {member.mention}\n-# FTSL Bot — Ticket System"),
    ))
    view.add_item(ui.ActionRow(
        ui.Button(label="Remind Support",  style=discord.ButtonStyle.secondary, custom_id=f"remind_support:{channel.id}"),
        ui.Button(label="Request Close",   style=discord.ButtonStyle.danger,    custom_id=f"request_close:{member.id}"),
        ui.Button(label="Mark as Priority", style=discord.ButtonStyle.primary,  custom_id=f"mark_priority:{channel.id}"),
    ))

    await channel.send(view=view)
    await interaction.followup.send(f"Your ticket has been opened: {channel.mention}", ephemeral=True)


# ══════════════════════════════════════════════════════════════════════════════
#  Select
# ══════════════════════════════════════════════════════════════════════════════

class TicketTypeSelect(ui.Select):
    def __init__(self):
        super().__init__(
            placeholder="Open a ticket...",
            min_values=1, max_values=1,
            options=[
                discord.SelectOption(label="Purchase", value="purchase",
                    description="Open a ticket to buy something from FTSL."),
                discord.SelectOption(label="Support",  value="support",
                    description="Open a ticket for help or an issue."),
            ],
            custom_id="ticket_type_select",
        )

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "purchase":
            await interaction.response.send_modal(PurchaseModal())
        else:
            await interaction.response.send_modal(SupportModal())


class PersistentPanelView(ui.LayoutView):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(ui.ActionRow(TicketTypeSelect()))


# ══════════════════════════════════════════════════════════════════════════════
#  Cog
# ══════════════════════════════════════════════════════════════════════════════

class TicketsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.bot.add_view(PersistentPanelView())

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        if interaction.type != discord.InteractionType.component:
            return
        custom_id: str = interaction.data.get("custom_id", "")

        # ── Remind Support ───────────────────────────────────────────────────
        if custom_id.startswith("remind_support:"):
            channel_id = int(custom_id.split(":")[1])
            now  = time.time()
            last = _remind_cooldowns.get(channel_id, 0)
            if last != 0 and (now - last) < REMIND_COOLDOWN:
                remaining  = int(REMIND_COOLDOWN - (now - last))
                hrs, rem   = divmod(remaining, 3600)
                mins, secs = divmod(rem, 60)
                await interaction.response.send_message(
                    f"You can remind support again in **{hrs}h {mins}m {secs}s**.", ephemeral=True
                )
                return
            _remind_cooldowns[channel_id] = now
            support_role = interaction.guild.get_role(SUPPORT_ROLE_ID)
            mention = support_role.mention if support_role else "@Support"
            view = ui.LayoutView()
            view.add_item(ui.Container(ui.TextDisplay(
                f"## Support Reminder\n{mention} — {interaction.user.mention} is still waiting for a response."
            )))
            await interaction.response.send_message(view=view)

        # ── Mark Priority ────────────────────────────────────────────────────
        elif custom_id.startswith("mark_priority:"):
            channel = interaction.channel
            if not channel.name.startswith("priority-"):
                new_name = "priority-" + channel.name
                await channel.edit(name=new_name)
                founder_role = interaction.guild.get_role(FOUNDER_ROLE_ID)
                mention = founder_role.mention if founder_role else "@Founder"
                view = ui.LayoutView()
                view.add_item(ui.Container(ui.TextDisplay(
                    f"## Priority Ticket\nThis ticket has been marked as priority by {interaction.user.mention}.\n{mention}, please attend to this as soon as possible."
                )))
                await interaction.response.send_message(view=view)
            else:
                await interaction.response.send_message(
                    "This ticket is already marked as priority.", ephemeral=True
                )

        # ── Request Close ────────────────────────────────────────────────────
        elif custom_id.startswith("request_close:"):
            founder_role = interaction.guild.get_role(FOUNDER_ROLE_ID)
            mention = founder_role.mention if founder_role else "@Founder"
            view = ui.LayoutView()
            view.add_item(ui.Container(
                ui.TextDisplay(
                    f"## Close Request\n{interaction.user.mention} has requested this ticket be closed.\n\n"
                    f"{mention}, would you like to go ahead and close it?"
                ),
                ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
                ui.TextDisplay("-# Only the Founder role can confirm closure."),
            ))
            view.add_item(ui.ActionRow(
                ui.Button(label="Close Ticket", style=discord.ButtonStyle.danger, custom_id="confirm_close")
            ))
            await interaction.response.send_message(view=view)

        # ── Confirm Close ────────────────────────────────────────────────────
        elif custom_id == "confirm_close":
            founder_role = interaction.guild.get_role(FOUNDER_ROLE_ID)
            if founder_role not in interaction.user.roles:
                await interaction.response.send_message(
                    "Only members with the Founder role can close tickets.", ephemeral=True
                )
                return
            channel   = interaction.channel
            opener_id = _ticket_openers.get(channel.id, 0)
            view = ui.LayoutView()
            view.add_item(ui.Container(ui.TextDisplay(
                f"## Ticket Closed\nClosed by {interaction.user.mention}. Saving transcript and deleting in 5 seconds."
            )))
            await interaction.response.send_message(view=view)
            await post_transcript(interaction.guild, channel, interaction.user, opener_id)
            await asyncio.sleep(5)
            _ticket_openers.pop(channel.id, None)
            _ticket_types.pop(channel.id, None)
            _remind_cooldowns.pop(channel.id, None)
            await channel.delete(reason=f"Ticket closed by {interaction.user}")
            await cleanup_empty_categories(interaction.guild)

    # ── /ticketpanel ─────────────────────────────────────────────────────────
    @app_commands.command(name="ticketpanel", description="Send the FTSL ticket panel.")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def ticketpanel(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        await interaction.channel.send(view=build_panel_view())
        await interaction.followup.send("Ticket panel sent.", ephemeral=True)

    # ── /closeticket ─────────────────────────────────────────────────────────
    @app_commands.command(name="closeticket", description="Immediately close this ticket (Founder only).")
    async def closeticket(self, interaction: discord.Interaction):
        founder_role = interaction.guild.get_role(FOUNDER_ROLE_ID)
        if founder_role not in interaction.user.roles:
            await interaction.response.send_message("Only the Founder role can use this command.", ephemeral=True)
            return
        channel   = interaction.channel
        opener_id = _ticket_openers.get(channel.id, 0)
        view = ui.LayoutView()
        view.add_item(ui.Container(ui.TextDisplay(
            f"## Ticket Closed\nClosed by {interaction.user.mention}. Saving transcript and deleting in 5 seconds."
        )))
        await interaction.response.send_message(view=view)
        await post_transcript(interaction.guild, channel, interaction.user, opener_id)
        await asyncio.sleep(5)
        _ticket_openers.pop(channel.id, None)
        _ticket_types.pop(channel.id, None)
        _remind_cooldowns.pop(channel.id, None)
        await channel.delete(reason=f"Closed by {interaction.user}")
        await cleanup_empty_categories(interaction.guild)

    # ── /adduser ─────────────────────────────────────────────────────────────
    @app_commands.command(name="adduser", description="Add a user to this ticket.")
    @app_commands.describe(member="The member to add")
    async def adduser(self, interaction: discord.Interaction, member: discord.Member):
        if not is_staff(interaction.user):
            await interaction.response.send_message("Only staff can add users to tickets.", ephemeral=True)
            return
        await interaction.channel.set_permissions(member,
            view_channel=True, send_messages=True, read_message_history=True
        )
        await interaction.response.send_message(f"{member.mention} has been added to this ticket.")

    # ── /removeuser ──────────────────────────────────────────────────────────
    @app_commands.command(name="removeuser", description="Remove a user from this ticket.")
    @app_commands.describe(member="The member to remove")
    async def removeuser(self, interaction: discord.Interaction, member: discord.Member):
        if not is_staff(interaction.user):
            await interaction.response.send_message("Only staff can remove users from tickets.", ephemeral=True)
            return
        await interaction.channel.set_permissions(member, overwrite=None)
        await interaction.response.send_message(f"{member.mention} has been removed from this ticket.")


async def setup(bot: commands.Bot):
    await bot.add_cog(TicketsCog(bot))
