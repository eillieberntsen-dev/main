import discord
from discord.ext import commands
from discord import app_commands
import json
import os
import time
import io

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = 1568277964762648657

STAFF_ROLES = [
    1568292371035193496,
    1568292367755116615,
    1568292377725247550,
    1568295300613939460,
]

MODERATOR_ROLES = [
    1568292371035193496,
    1568292367755116615,
]

SCAMMER_ROLE_ID = 1568292380862583045
RATTER_ROLE_ID  = 1568292391197085816

CHANNEL_CREATE_CATEGORY_ID = 1568291291480072313

CATEGORY_MAP = {
    "Channel":     1568354090520674485,
    "Support":     1568354171281743922,
    "Application": 1568354223354019860,
}

TRANSCRIPT_CHANNEL_ID = 1568360086571712663

MAX_TICKETS = 1
PING_COOLDOWN_SECONDS = 86400

DATA_FILE = "bot_data.json"

BANNER_URL = "https://cdn.discordapp.com/attachments/1515618623425871994/1568766028920655983/Render-Comp.gif?ex=6af102b7&is=6aefb137&hm=e9bf6c3291dc673f0e09ed7150807d60fec7034c384fd30b13f5f8444aa92170&"
EMBED_COLOR = 0x000000
FOOTER_TEXT = "Pasters Heaven · Best Provider For Tools And Sources"


def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {"tickets": {}, "ping_cooldowns": {}, "ticket_count": 0}


def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)


def make_embed(title=None, description=None, with_banner=True) -> discord.Embed:
    embed = discord.Embed(color=EMBED_COLOR, title=title, description=description)
    embed.set_footer(text=FOOTER_TEXT)
    if with_banner:
        embed.set_image(url=BANNER_URL)
    return embed


def has_staff_role():
    async def predicate(interaction: discord.Interaction):
        return any(role.id in STAFF_ROLES for role in interaction.user.roles)
    return app_commands.check(predicate)


def has_mod_role():
    async def predicate(interaction: discord.Interaction):
        return any(role.id in MODERATOR_ROLES for role in interaction.user.roles)
    return app_commands.check(predicate)


intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree


async def save_transcript(channel: discord.TextChannel, ticket_owner: discord.Member, ticket_number: int, ticket_type: str):
    lines = [
        "Paster Heaven — Ticket Transcript",
        f"Ticket: #{str(ticket_number).zfill(4)} | Type: {ticket_type}",
        f"Opened by: {ticket_owner} ({ticket_owner.id})",
        f"Channel: #{channel.name}",
        f"Closed at: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}",
        "=" * 60,
        "",
    ]

    async for msg in channel.history(limit=500, oldest_first=True):
        ts = msg.created_at.strftime("%Y-%m-%d %H:%M:%S")
        content = msg.content or ""
        if msg.embeds:
            for e in msg.embeds:
                if e.title:
                    content += f" [Embed: {e.title}]"
                if e.description:
                    content += f" {e.description}"
        if msg.attachments:
            for a in msg.attachments:
                content += f" [Attachment: {a.url}]"
        lines.append(f"[{ts}] {msg.author} — {content}")

    transcript_bytes = "\n".join(lines).encode("utf-8")
    filename = f"transcript-{channel.name}.txt"

    transcript_embed = make_embed(
        title="📄 Ticket Transcript",
        description=(
            f"**Ticket:** `#{str(ticket_number).zfill(4)}` · **Type:** {ticket_type}\n"
            f"**Opened by:** {ticket_owner.mention}\n"
            f"**Channel:** `#{channel.name}`"
        ),
    )

    transcript_channel = channel.guild.get_channel(TRANSCRIPT_CHANNEL_ID)
    if transcript_channel:
        await transcript_channel.send(
            embed=transcript_embed,
            file=discord.File(io.BytesIO(transcript_bytes), filename=filename),
        )

    try:
        await ticket_owner.send(
            embed=transcript_embed,
            file=discord.File(io.BytesIO(transcript_bytes), filename=filename),
        )
    except discord.Forbidden:
        pass


class TicketView(discord.ui.View):
    def __init__(self, ticket_owner_id: int, claimed_by_id: int = None):
        super().__init__(timeout=None)
        self.ticket_owner_id = ticket_owner_id
        self.claimed_by_id = claimed_by_id
        self._refresh_buttons()

    def _refresh_buttons(self):
        self.clear_items()

        close_btn = discord.ui.Button(
            label="Close",
            style=discord.ButtonStyle.danger,
            emoji="🔒",
            custom_id=f"ticket_close_{self.ticket_owner_id}",
        )
        close_btn.callback = self.close_callback
        self.add_item(close_btn)

        if self.claimed_by_id is None:
            claim_btn = discord.ui.Button(
                label="Claim",
                style=discord.ButtonStyle.success,
                emoji="✋",
                custom_id=f"ticket_claim_{self.ticket_owner_id}",
            )
            claim_btn.callback = self.claim_callback
            self.add_item(claim_btn)

    async def close_callback(self, interaction: discord.Interaction):
        if not any(role.id in STAFF_ROLES for role in interaction.user.roles):
            await interaction.response.send_message("❌ Only staff can close tickets.", ephemeral=True)
            return

        data = load_data()
        ch_id = str(interaction.channel.id)
        ticket_info = data["tickets"].get(ch_id, {})
        ticket_number = ticket_info.get("ticket_number", 0)
        ticket_type = ticket_info.get("ticket_type", "Unknown")
        owner_id = ticket_info.get("user_id")

        await interaction.response.send_message("🔒 Saving transcript and closing ticket in 5 seconds...")

        owner = interaction.guild.get_member(owner_id) if owner_id else None
        if owner:
            await save_transcript(interaction.channel, owner, ticket_number, ticket_type)

        import asyncio
        await asyncio.sleep(5)

        if ch_id in data["tickets"]:
            del data["tickets"][ch_id]
            save_data(data)

        await interaction.channel.delete(reason="Ticket closed")

    async def claim_callback(self, interaction: discord.Interaction):
        if not any(role.id in STAFF_ROLES for role in interaction.user.roles):
            await interaction.response.send_message("❌ Only staff can claim tickets.", ephemeral=True)
            return

        self.claimed_by_id = interaction.user.id
        self._refresh_buttons()

        data = load_data()
        ch_id = str(interaction.channel.id)
        if ch_id in data["tickets"]:
            data["tickets"][ch_id]["claimed_by"] = interaction.user.id
            save_data(data)

        claimed_embed = make_embed(
            title="## Ticket Claimed",
            description=f"{interaction.user.mention} is now handling this ticket.",
        )
        await interaction.response.send_message(embed=claimed_embed)

        async for msg in interaction.channel.history(oldest_first=True, limit=5):
            if msg.author == bot.user and msg.embeds:
                old = msg.embeds[0]
                new_embed = make_embed(title=old.title, description=old.description)
                new_embed.add_field(name="Status", value=f"Claimed by {interaction.user.mention}", inline=False)
                await msg.edit(embed=new_embed, view=self)
                break


class TicketCategorySelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Channel",     description="Questions & access regarding channels", emoji="<:c_:1568305255727370320>"),
            discord.SelectOption(label="Support",     description="Orders, products & technical issues",   emoji="<:warning2:1568294327346536458>"),
            discord.SelectOption(label="Staff Apply", description="Apply to become part of our team",      emoji="<:RUSH_staff:1568294334929830071>"),
        ]
        super().__init__(
            placeholder="Select an option to open your ticket...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="ticket_category_select",
        )

    async def callback(self, interaction: discord.Interaction):
        data = load_data()
        guild = interaction.guild
        user = interaction.user

        user_tickets = [
            ch_id for ch_id, info in data["tickets"].items()
            if info.get("user_id") == user.id
        ]

        if len(user_tickets) >= MAX_TICKETS:
            await interaction.response.send_message(
                f"❌ You already have {MAX_TICKETS} open tickets. Please wait for one to be closed.",
                ephemeral=True,
            )
            return

        chosen = self.values[0]
        category_id = CATEGORY_MAP.get(chosen)
        category = guild.get_channel(category_id)
        if category is None:
            await interaction.response.send_message("❌ Ticket category not found.", ephemeral=True)
            return

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
        }
        for role_id in STAFF_ROLES:
            role = guild.get_role(role_id)
            if role:
                overwrites[role] = discord.PermissionOverwrite(
                    view_channel=True, send_messages=True, read_message_history=True
                )

        data["ticket_count"] = data.get("ticket_count", 0) + 1
        ticket_number = data["ticket_count"]
        ticket_num_str = str(ticket_number).zfill(4)

        slug_map = {
            "Channel":     "channel",
            "Support":     "support",
            "Staff Apply": "staff-apply",
        }
        channel_name = f"{user.name}-{slug_map[chosen]}"

        channel = await guild.create_text_channel(
            name=channel_name,
            category=category,
            overwrites=overwrites,
        )

        data["tickets"][str(channel.id)] = {
            "user_id": user.id,
            "channel_name": channel.name,
            "ticket_number": ticket_number,
            "ticket_type": chosen,
            "claimed_by": None,
        }
        save_data(data)

        opened_ts = int(time.time())

        issue_line = "\n**Issue:** *(Please describe your situation below)*" if chosen == "Support" else ""

        description = (
            f"## {chosen} Ticket\n\n"
            f"**Opened by:** {user.mention}\n"
            f"**Ticket:** `#{ticket_num_str}` · opened <t:{opened_ts}:R>"
            f"{issue_line}\n\n"
            f"> <a:51047animatedarrowwhite:1568294336876257300> Please describe your situation in detail below.\n"
            f"> <a:51047animatedarrowwhite:1568294336876257300> Our support team has been notified and will try to help you shortly."
        )

        embed = make_embed(description=description)
        view = TicketView(ticket_owner_id=user.id)
        await channel.send(embed=embed, view=view)

        await interaction.response.send_message(
            f"✅ Your **{chosen}** ticket has been created: {channel.mention}", ephemeral=True
        )


class TicketPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketCategorySelect())


@tree.command(name="ticket-panel", description="Send the support ticket panel", guild=discord.Object(id=GUILD_ID))
async def ticket_panel(interaction: discord.Interaction):
    description = (
        "## **Paster Heaven — Ticket Center**\n\n"
        "*Need assistance or want to get started? Open a ticket below and our team will help you as soon as possible!*\n\n"
        "<:c_:1568305255727370320> **Channels**\n"
        "> <a:51047animatedarrowwhite:1568294336876257300> Questions regarding our channels\n"
        "> <a:51047animatedarrowwhite:1568294336876257300> Channel access & channel-related issues\n\n"
        "<:warning2:1568294327346536458> **Support**\n"
        "> <a:51047animatedarrowwhite:1568294336876257300> Existing orders & product assistance\n"
        "> <a:51047animatedarrowwhite:1568294336876257300> Technical issues & troubleshooting\n\n"
        "<:RUSH_staff:1568294334929830071> **Application**\n"
        "> <a:51047animatedarrowwhite:1568294336876257300> Apply to become part of our team\n"
        "> <a:51047animatedarrowwhite:1568294336876257300> Staff applications & inquiries\n\n"
        "*Select an option below to open your ticket!*"
    )
    embed = make_embed(description=description)
    view = TicketPanelView()
    await interaction.response.send_message(embed=embed, view=view)


@tree.command(name="channel-create", description="Create a channel for a user", guild=discord.Object(id=GUILD_ID))
@has_staff_role()
@app_commands.describe(user="The user to create a channel for", name="Channel name")
async def channel_create(interaction: discord.Interaction, user: discord.Member, name: str):
    guild = interaction.guild
    category = guild.get_channel(CHANNEL_CREATE_CATEGORY_ID)

    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
    }
    for role_id in STAFF_ROLES:
        role = guild.get_role(role_id)
        if role:
            overwrites[role] = discord.PermissionOverwrite(
                view_channel=True, send_messages=True, read_message_history=True
            )

    channel = await guild.create_text_channel(
        name=f"🌐┃{name}",
        category=category,
        overwrites=overwrites,
    )

    embed = make_embed(description=f"✅ Channel created for {user.mention}: {channel.mention}")
    await interaction.response.send_message(embed=embed, ephemeral=True)


@tree.command(name="channel-ping", description="Ping @here in your channel (once per 24 hours)", guild=discord.Object(id=GUILD_ID))
async def channel_ping(interaction: discord.Interaction):
    data = load_data()
    user_id = str(interaction.user.id)
    now = time.time()

    last_ping = data["ping_cooldowns"].get(user_id, 0)
    elapsed = now - last_ping

    if elapsed < PING_COOLDOWN_SECONDS:
        reset_ts = int(last_ping + PING_COOLDOWN_SECONDS)
        await interaction.response.send_message(
            f"⏳ 24 Hours Haven't Gone — <t:{reset_ts}:R> left",
            ephemeral=True,
        )
        return

    data["ping_cooldowns"][user_id] = now
    save_data(data)

    await interaction.response.send_message(f"@here — pinged by {interaction.user.mention}")


@tree.command(name="scammer-alert", description="Report a scammer or ratter", guild=discord.Object(id=GUILD_ID))
@has_mod_role()
@app_commands.describe(user="The user to report", reason="Reason: Scamming or Ratting")
@app_commands.choices(reason=[
    app_commands.Choice(name="Scamming", value="scamming"),
    app_commands.Choice(name="Ratting",  value="ratting"),
])
async def scammer_alert(interaction: discord.Interaction, user: discord.Member, reason: app_commands.Choice[str]):
    guild = interaction.guild

    if reason.value == "scamming":
        role  = guild.get_role(SCAMMER_ROLE_ID)
        label = "Scammer"
    else:
        role  = guild.get_role(RATTER_ROLE_ID)
        label = "Ratter"

    if role is None:
        await interaction.response.send_message("❌ Role not found.", ephemeral=True)
        return

    await user.add_roles(role, reason=f"Reported by {interaction.user} for {reason.value}")

    embed = make_embed(
        title=f"🚨 Scammer Alert — {label}",
        description=f"{user.mention} has been flagged as a **{label}**.\n**Reported by:** {interaction.user.mention}",
    )
    embed.set_thumbnail(url=user.display_avatar.url)
    await interaction.response.send_message(embed=embed)


@tree.command(name="ticket-purge", description="Delete all active tickets", guild=discord.Object(id=GUILD_ID))
@has_staff_role()
async def ticket_purge(interaction: discord.Interaction):
    data = load_data()
    guild = interaction.guild
    deleted = 0

    await interaction.response.defer(ephemeral=True)

    for ch_id in list(data["tickets"].keys()):
        channel = guild.get_channel(int(ch_id))
        if channel:
            await channel.delete(reason="Ticket purge")
            deleted += 1
        del data["tickets"][ch_id]

    save_data(data)

    embed = make_embed(description=f"✅ Purged {deleted} ticket(s).")
    await interaction.followup.send(embed=embed, ephemeral=True)


@tree.command(name="ticket-rename", description="Rename the current ticket channel", guild=discord.Object(id=GUILD_ID))
@has_staff_role()
@app_commands.describe(name="New name for this ticket")
async def ticket_rename(interaction: discord.Interaction, name: str):
    data = load_data()
    channel = interaction.channel

    if str(channel.id) not in data["tickets"]:
        await interaction.response.send_message("❌ This command can only be used inside a ticket channel.", ephemeral=True)
        return

    safe_name = name.lower().replace(" ", "-")[:100]
    await channel.edit(name=safe_name)

    data["tickets"][str(channel.id)]["channel_name"] = safe_name
    save_data(data)

    embed = make_embed(description=f"✅ Ticket renamed to `{safe_name}`.")
    await interaction.response.send_message(embed=embed)


@tree.command(name="json-embed", description="Send an embed from a JSON file", guild=discord.Object(id=GUILD_ID))
@has_staff_role()
@app_commands.describe(file="A .json file containing the embed data")
async def json_embed(interaction: discord.Interaction, file: discord.Attachment):
    if not file.filename.endswith(".json"):
        await interaction.response.send_message("❌ Please upload a `.json` file.", ephemeral=True)
        return

    if file.size > 512_000:
        await interaction.response.send_message("❌ File is too large.", ephemeral=True)
        return

    raw = await file.read()
    try:
        data = json.loads(raw.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        await interaction.response.send_message(f"❌ Invalid JSON: `{e}`", ephemeral=True)
        return

    if "embeds" in data:
        embed_data_list = data["embeds"]
    elif isinstance(data, list):
        embed_data_list = data
    else:
        embed_data_list = [data]

    embeds = []
    for ed in embed_data_list[:10]:
        try:
            embeds.append(discord.Embed.from_dict(ed))
        except Exception as e:
            await interaction.response.send_message(f"❌ Failed to parse embed: `{e}`", ephemeral=True)
            return

    content = data.get("content", None) if isinstance(data, dict) else None

    await interaction.response.send_message("✅ Sending embed...", ephemeral=True)
    await interaction.channel.send(content=content, embeds=embeds)


@bot.event
async def on_ready():
    bot.add_view(TicketPanelView())
    await tree.sync(guild=discord.Object(id=GUILD_ID))
    print(f"Logged in as {bot.user} — commands synced.")


bot.run(TOKEN)
