import os
import logging
import asyncio
from collections import deque
from dotenv import load_dotenv
import discord
from discord.ext import commands
import yt_dlp as youtube_dl

# Load environment variables
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)

# Suppress noise about yt-dlp
youtube_dl.utils.bug_reports_message = lambda: ""

# FFmpeg options
FFMPEG_OPTIONS = {
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    "options": "-vn"
}

# YT-DLP options
YTDL_OPTIONS = {
    "format": "bestaudio/best",
    "extractaudio": True,
    "audioformat": "mp3",
    "outtmpl": "%(extractor)s-%(id)s-%(title)s.%(ext)s",
    "restrictfilenames": True,
    "noplaylist": True,
    "nocheckcertificate": True,
    "ignoreerrors": False,
    "logtostderr": False,
    "quiet": True,
    "no_warnings": True,
    "default_search": "auto",
    "source_address": "0.0.0.0"
}

# Initialize bot
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# MusicPlayer class
class MusicPlayer:
    def __init__(self, bot):
        self.queue = deque()
        self.current_song = None
        self.loop = False
        self.voice_client = None
        self.bot = bot  # Pass the bot instance to access the event loop

    def play_next_song(self, error=None):
        if error:
            logging.error(f"Playback error: {error}")

        if self.loop and self.current_song:
            self.queue.appendleft(self.current_song)

        if self.queue:
            self.current_song = self.queue.popleft()
            source = discord.FFmpegPCMAudio(self.current_song["url"], **FFMPEG_OPTIONS)
            self.voice_client.play(source, after=self.play_next_song)
        else:
            self.current_song = None
            asyncio.run_coroutine_threadsafe(self.voice_client.disconnect(), self.bot.loop)

    async def add_to_queue(self, song):
        self.queue.append(song)
        if not self.voice_client.is_playing() and not self.voice_client.is_paused():
            self.play_next_song()

# Initialize MusicPlayer
music_player = MusicPlayer(bot)

# Bot commands
@bot.event
async def on_ready():
    logging.info(f"Logged in as {bot.user.name}")

@bot.command(name="play")
async def play(ctx, *, query: str):
    if not ctx.author.voice:
        await ctx.send("You are not connected to a voice channel.")
        return

    if not music_player.voice_client:
        music_player.voice_client = await ctx.author.voice.channel.connect()

    with youtube_dl.YoutubeDL(YTDL_OPTIONS) as ydl:
        info = ydl.extract_info(f"ytsearch:{query}", download=False)["entries"][0]
        song = {
            "title": info["title"],
            "url": info["url"]
        }
        await music_player.add_to_queue(song)
        await ctx.send(f"Added to queue: **{song['title']}**")

@bot.command(name="skip")
async def skip(ctx):
    if music_player.voice_client and music_player.voice_client.is_playing():
        music_player.voice_client.stop()
        await ctx.send("Skipped the current song.")
    else:
        await ctx.send("No song is currently playing.")

@bot.command(name="stop")
async def stop(ctx):
    if music_player.voice_client:
        music_player.queue.clear()
        music_player.voice_client.stop()
        await music_player.voice_client.disconnect()
        await ctx.send("Stopped playback and cleared the queue.")
    else:
        await ctx.send("The bot is not connected to a voice channel.")

@bot.command(name="queue")
async def queue(ctx):
    if not music_player.queue:
        await ctx.send("The queue is empty.")
        return

    embed = discord.Embed(title="Song Queue", color=discord.Color.blue())
    embed.add_field(name="Now Playing", value=music_player.current_song["title"], inline=False)
    for i, song in enumerate(music_player.queue, start=1):
        embed.add_field(name=f"{i}. {song['title']}", value="\u200b", inline=False)
    await ctx.send(embed=embed)

@bot.command(name="loop")
async def loop(ctx):
    music_player.loop = not music_player.loop
    await ctx.send(f"Looping is now {'**on**' if music_player.loop else '**off**'}.")

# Run the bot
if __name__ == "__main__":
    bot.run(BOT_TOKEN)