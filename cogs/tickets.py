"""
FTSL Bot — Ticket System (discord.py 2.6+)
Uses Components V2: LayoutView, Container, TextDisplay, Separator, ActionRow.
"""

import discord
from discord import app_commands, ui
from discord.ext import commands
import asyncio
import time

# ─── Role IDs ────────────────────────────────────────────────────────────────
FOUNDER_ROLE_ID = 1500217835950047323   # Can close tickets after request
SUPPORT_ROLE_ID = 1500217897166049351   # Pinged at ticket open

# ─── Category names ──────────────────────────────────────────────────────────
PURCHASE_CATEGORY = "Purchase Tickets"
SUPPORT_CATEGORY  = "Support Tickets"

# ─── Remind cooldown (seconds) ───────────────────────────────────────────────
REMIND_COOLDOWN = 3600  # 1 hour

# ─── Remind cooldown store ───────────────────────────────────────────────────
_remind_cooldowns: dict[int, float] = {}   # channel_id -> last_used unix timestamp


# ══════════════════════════════════════════════════════════════════════════════
#  Helpers
# ══════════════════════════════════════════════════════════════════════════════

async def get_or_create_category(guild: discord.Guild, name: str) -> discord.CategoryChannel:
    cat = discord.utils.get(guild.categories, name=name)
    if cat is None:
        cat = await guild.create_category(name)
    return cat


async def cleanup_empty_categories(guild: discord.Guild):
    """Delete Purchase/Support categories when they have no channels left."""
    for cat_name in (PURCHASE_CATEGORY, SUPPORT_CATEGORY):
        cat = discord.utils.get(guild.categories, name=cat_name)
        if cat and len(cat.channels) == 0:
            await cat.delete(reason="No ticket channels remaining.")


# ══════════════════════════════════════════════════════════════════════════════
#  Panel builder
# ══════════════════════════════════════════════════════════════════════════════

def build_panel_view() -> ui.LayoutView:
    view = ui.LayoutView()

    container = ui.Container(
        ui.TextDisplay("## FTSL Ticket System"),
        ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
        ui.TextDisplay(
            "Need help or looking to make a purchase? Open a ticket below and someone from our team will be with you shortly.\n\n"
            "**Purchase** — Select this if you're interested in buying something from us. You'll be asked to fill out a short form with the details.\n\n"
            "**Support** — Select this if you're running into an issue or need assistance with something. Describe your situation and we'll get back to you as soon as possible."
        ),
        ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
        ui.TextDisplay("-# FTSL Bot — Ticket System"),
    )
    view.add_item(container)

    row = ui.ActionRow(TicketTypeSelect())
    view.add_item(row)

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
        await open_ticket(
            interaction,
            ticket_type="purchase",
            extra={
                "what": self.what_to_buy.value,
                "payment": self.payment_method.value,
            },
        )


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
        await open_ticket(
            interaction,
            ticket_type="support",
            extra={
                "issue": self.issue.value,
                "help_needed": self.help_needed.value,
            },
        )


# ══════════════════════════════════════════════════════════════════════════════
#  Ticket open logic
# ══════════════════════════════════════════════════════════════════════════════

async def open_ticket(
    interaction: discord.Interaction,
    ticket_type: str,
    extra: dict,
):
    guild  = interaction.guild
    member = interaction.user

    cat_name     = PURCHASE_CATEGORY if ticket_type == "purchase" else SUPPORT_CATEGORY
    channel_name = f"{ticket_type}-{member.name.lower()}"

    # ── Duplicate check ──────────────────────────────────────────────────────
    category = await get_or_create_category(guild, cat_name)
    existing = discord.utils.get(category.channels, name=channel_name)
    if existing:
        await interaction.followup.send(
            f"You already have an open ticket: {existing.mention}",
            ephemeral=True,
        )
        return

    # ── Channel permissions ──────────────────────────────────────────────────
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

    # ── Create channel ───────────────────────────────────────────────────────
    channel = await category.create_text_channel(
        name=channel_name,
        overwrites=overwrites,
        topic=f"Ticket opened by {member} ({member.id}) | Type: {ticket_type}",
    )

    # ── Support role ping ────────────────────────────────────────────────────
    if support_role:
        await channel.send(support_role.mention)

    # ── Build ticket message ─────────────────────────────────────────────────
    if ticket_type == "purchase":
        header  = f"## Purchase Ticket — {member.display_name}"
        intro   = (
            "Thanks for reaching out. Someone from our team will be with you shortly.\n"
            "Here's a summary of what you submitted:"
        )
        details = (
            "**Purchase Details**\n"
            f"```\nItem / Service : {extra['what']}\n"
            f"Payment Method : {extra['payment']}\n```"
        )
    else:
        header  = f"## Support Ticket — {member.display_name}"
        intro   = (
            "Thanks for opening a ticket. A support member will be with you as soon as possible.\n"
            "Here's a summary of what you submitted:"
        )
        details = (
            "**Issue Details**\n"
            f"```\nIssue       : {extra['issue']}\n"
            f"Help Needed : {extra['help_needed']}\n```"
        )

    remind_btn = ui.Button(
        label="Remind Support",
        style=discord.ButtonStyle.secondary,
        custom_id=f"remind_support:{channel.id}",
    )
    close_btn = ui.Button(
        label="Request Close",
        style=discord.ButtonStyle.danger,
        custom_id=f"request_close:{member.id}",
    )
    btn_row = ui.ActionRow(remind_btn, close_btn)

    view = ui.LayoutView()
    view.add_item(ui.Container(
        ui.TextDisplay(header),
        ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
        ui.TextDisplay(intro),
        ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
        ui.TextDisplay(details),
        ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
        ui.TextDisplay(
            f"**Opened by:** {member.mention}\n"
            "-# FTSL Bot — Ticket System"
        ),
    ))
    view.add_item(btn_row)

    await channel.send(view=view)

    _remind_cooldowns[channel.id] = 0

    await interaction.followup.send(
        f"Your ticket has been opened: {channel.mention}",
        ephemeral=True,
    )


# ══════════════════════════════════════════════════════════════════════════════
#  Select menu
# ══════════════════════════════════════════════════════════════════════════════

class TicketTypeSelect(ui.Select):
    def __init__(self):
        super().__init__(
            placeholder="Open a ticket...",
            min_values=1,
            max_values=1,
            options=[
                discord.SelectOption(
                    label="Purchase",
                    value="purchase",
                    description="Open a ticket to buy something from FTSL.",
                ),
                discord.SelectOption(
                    label="Support",
                    value="support",
                    description="Open a ticket for help or an issue.",
                ),
            ],
            custom_id="ticket_type_select",
        )

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "purchase":
            await interaction.response.send_modal(PurchaseModal())
        else:
            await interaction.response.send_modal(SupportModal())


# ══════════════════════════════════════════════════════════════════════════════
#  Persistent panel view
# ══════════════════════════════════════════════════════════════════════════════

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
                    f"You can remind support again in **{hrs}h {mins}m {secs}s**.",
                    ephemeral=True,
                )
                return

            _remind_cooldowns[channel_id] = now
            support_role = interaction.guild.get_role(SUPPORT_ROLE_ID)
            mention = support_role.mention if support_role else "@Support"

            view = ui.LayoutView()
            view.add_item(ui.Container(
                ui.TextDisplay(
                    f"## Support Reminder\n"
                    f"{mention} — {interaction.user.mention} is still waiting for a response in this ticket."
                ),
            ))
            await interaction.response.send_message(view=view)

        # ── Request Close ────────────────────────────────────────────────────
        elif custom_id.startswith("request_close:"):
            founder_role = interaction.guild.get_role(FOUNDER_ROLE_ID)
            mention = founder_role.mention if founder_role else "@Founder"

            confirm_btn = ui.Button(
                label="Close Ticket",
                style=discord.ButtonStyle.danger,
                custom_id="confirm_close",
            )

            view = ui.LayoutView()
            view.add_item(ui.Container(
                ui.TextDisplay(
                    f"## Close Request\n"
                    f"{interaction.user.mention} has requested this ticket be closed.\n\n"
                    f"{mention}, would you like to go ahead and close it?"
                ),
                ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
                ui.TextDisplay("-# Only the Founder role can confirm closure."),
            ))
            view.add_item(ui.ActionRow(confirm_btn))
            await interaction.response.send_message(view=view)

        # ── Confirm Close ────────────────────────────────────────────────────
        elif custom_id == "confirm_close":
            founder_role = interaction.guild.get_role(FOUNDER_ROLE_ID)
            if founder_role not in interaction.user.roles:
                await interaction.response.send_message(
                    "Only members with the Founder role can close tickets.",
                    ephemeral=True,
                )
                return

            channel = interaction.channel
            view = ui.LayoutView()
            view.add_item(ui.Container(
                ui.TextDisplay(
                    f"## Ticket Closed\n"
                    f"Closed by {interaction.user.mention}. This channel will be deleted in 5 seconds."
                ),
            ))
            await interaction.response.send_message(view=view)
            await asyncio.sleep(5)
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
            await interaction.response.send_message(
                "Only the Founder role can use this command.",
                ephemeral=True,
            )
            return

        view = ui.LayoutView()
        view.add_item(ui.Container(
            ui.TextDisplay(
                f"## Ticket Closed\n"
                f"Closed by {interaction.user.mention}. Deleting in 5 seconds."
            ),
        ))
        await interaction.response.send_message(view=view)
        await asyncio.sleep(5)
        await interaction.channel.delete(reason=f"Closed by {interaction.user}")
        await cleanup_empty_categories(interaction.guild)


# ══════════════════════════════════════════════════════════════════════════════
#  Setup
# ══════════════════════════════════════════════════════════════════════════════

async def setup(bot: commands.Bot):
    await bot.add_cog(TicketsCog(bot))
