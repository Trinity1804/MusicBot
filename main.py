import discord
from discord.ext import commands
import asyncio
import yt_dlp
import dotenv

BOT_TOKEN = dotenv.get_key(".env", "BOT_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

YTDL_OPTIONS = {
    'format': 'bestaudio/best',
    'noplaylist': True,
    'quiet': True,
    'default_search': 'ytsearch'  
}

FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn'
}

class Song:
    def __init__(self, source, title):
        self.source = source
        self.title = title

class MusicPlayer:
    def __init__(self):
        self.queue = asyncio.Queue()
        self.current = None
        self.loop = False
        self.voice_client = None
        self.play_next_song = asyncio.Event()
    
    async def audio_player_task(self):
        while True:
            self.play_next_song.clear()
            self.current = await self.queue.get()
            if self.voice_client is not None:
                self.voice_client.play(
                    discord.FFmpegPCMAudio(self.current.source, **FFMPEG_OPTIONS),
                    after=lambda e: self.bot_loop.call_soon_threadsafe(self.play_next_song.set)
                )
                await self.play_next_song.wait()
                if self.loop:
                    await self.queue.put(self.current)
            else:
                while not self.queue.empty():
                    self.queue.get_nowait()

player = MusicPlayer()
player.bot_loop = bot.loop

def yt_search(url_or_term):
    if not url_or_term.startswith("http"):
        url_or_term = f"ytsearch1:{url_or_term}"
    with yt_dlp.YoutubeDL(YTDL_OPTIONS) as ytdl:
        try:
            info = ytdl.extract_info(url_or_term, download=False)
        except Exception:
            info = None
    if info is None:
        return None
    if 'entries' in info:
        info = info['entries'][0]
    return Song(info['url'], info.get('title', 'Unknown Title'))

@bot.command(name="join")
async def join(ctx):
    if ctx.author.voice:
        channel = ctx.author.voice.channel
        if ctx.voice_client is None:
            vc = await channel.connect()
            player.voice_client = vc
            bot.loop.create_task(player.audio_player_task())
        else:
            await ctx.voice_client.move_to(channel)
        await ctx.send(f"Joined {channel.name}")
    else:
        await ctx.send("You are not connected to a voice channel.")

@bot.command(name="play")
async def play(ctx, *, query: str):
    if ctx.author.voice is None:
        await ctx.send("Connect to a voice channel first.")
        return
    if ctx.voice_client is None:
        await join(ctx)
    song = yt_search(query)
    if song is None:
        await ctx.send("Could not retrieve song.")
        return
    await player.queue.put(song)
    await ctx.send(f"Queued: {song.title}")

@bot.command(name="queue")
async def queue_(ctx):
    if player.current:
        msg = f"Now playing: {player.current.title}\n"
    else:
        msg = "No song is playing currently.\n"
    if player.queue.empty():
        msg += "Queue is empty."
    else:
        msg += "Up next:\n"
        queue_list = list(player.queue._queue)
        for idx, s in enumerate(queue_list, 1):
            msg += f"{idx}. {s.title}\n"
    await ctx.send(msg)

@bot.command(name="skip")
async def skip(ctx):
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.stop()
        await ctx.send("Skipped the song.")
    else:
        await ctx.send("No song is playing.")

@bot.command(name="loop")
async def loop(ctx, mode: str):
    if mode.lower() == "on":
        player.loop = True
        await ctx.send("Looping enabled.")
    elif mode.lower() == "off":
        player.loop = False
        await ctx.send("Looping disabled.")
    else:
        await ctx.send("Use !loop on or !loop off.")

@bot.command(name="stop")
async def stop(ctx):
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        player.voice_client = None
        # Clear queue
        while not player.queue.empty():
            player.queue.get_nowait()
        await ctx.send("Stopped playback and disconnected.")
    else:
        await ctx.send("Not connected to any voice channel.")

@bot.command(name="pause")
async def pause(ctx):
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.pause()
        await ctx.send("Paused the song.")
    else:
        await ctx.send("No song is playing.")

@bot.command(name="resume")
async def resume(ctx):
    if ctx.voice_client and ctx.voice_client.is_paused():
        ctx.voice_client.resume()
        await ctx.send("Resumed the song.")
    else:
        await ctx.send("The song is not paused.")

bot.run(BOT_TOKEN)
