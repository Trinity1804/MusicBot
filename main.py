import discord
from discord.ext import commands
import yt_dlp
import os
from dotenv import load_dotenv
import asyncio
import logging
from collections import deque

# Load environment variables
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s:%(levelname)s:%(name)s: %(message)s",
    handlers=[
        logging.FileHandler(filename="bot.log", encoding="utf-8", mode="a"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("discord_bot")

# Intents
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.voice_states = True

# Initialize bot
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

# FFmpeg Options
FFMPEG_OPTIONS = {
    "options": "-vn",
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
}

# YT-DLP Options
YTDL_OPTIONS = {
    "format": "bestaudio/best",
    "noplaylist": True,
    "quiet": True,
    "default_search": "auto",
    "source_address": "0.0.0.0",  # Bind to IPv4 since IPv6 can cause issues
    "headers": {
        "User-Agent": "Mozilla/5.0",
        "Accept": "*/*",
        "Accept-Language": "en",
    },
}

ydl = yt_dlp.YoutubeDL(YTDL_OPTIONS)

# Dictionary to keep track of guild music players
music_players = {}


# Music Player Class
class MusicPlayer:
    def __init__(self, ctx):
        self.bot = ctx.bot
        self._guild = ctx.guild
        self._channel = ctx.channel
        self.queue = deque()
        self.is_looping = False
        self.voice_client = ctx.voice_client
        self.current = None
        self.is_playing = False
        self.skip_event = asyncio.Event()
        self.stop_event = asyncio.Event()
        self.player_task = self.bot.loop.create_task(self.player_loop())
        logger.info(f"Initialized MusicPlayer for guild: {self._guild.name}")

    async def player_loop(self):
        while True:
            if not self.queue:
                logger.info(
                    f"Queue empty for guild: {self._guild.name}, waiting for songs."
                )
                try:
                    # Wait for a song to be added or timeout after 5 minutes
                    await asyncio.wait_for(self.skip_event.wait(), timeout=300)
                except asyncio.TimeoutError:
                    if self.voice_client and not self.voice_client.is_playing():
                        await self.voice_client.disconnect()
                        logger.info(
                            f"Disconnected from guild: {self._guild.name} due to inactivity."
                        )
                        del music_players[self._guild.id]
                        break
                finally:
                    self.skip_event.clear()

            if self.queue:
                self.current = self.queue.popleft()
                logger.info(
                    f'Now playing: {self.current["title"]} in guild: {self._guild.name}'
                )
                try:
                    self.voice_client.play(
                        discord.FFmpegPCMAudio(self.current["url"], **FFMPEG_OPTIONS),
                        after=self.play_next_song,
                    )
                    self.is_playing = True
                except Exception as e:
                    logger.error(f"Error playing song: {e}")
                    await self._channel.send(f"Error playing song: {e}")
                    self.is_playing = False
            else:
                self.is_playing = False

            # Wait until the current song is finished or skipped
            await self.skip_event.wait()
            self.skip_event.clear()

    def play_next_song(self, error=None):
        if error:
            logger.error(f"Error in play_next_song: {error}")
            self.bot.loop.call_soon_threadsafe(self.skip_event.set)
            return
        if self.is_looping and self.current:
            logger.info(f'Looping song: {self.current["title"]}')
            self.queue.appendleft(self.current)
        self.bot.loop.call_soon_threadsafe(self.skip_event.set)

    def add_to_queue(self, song):
        self.queue.append(song)
        logger.info(f'Added to queue: {song["title"]} in guild: {self._guild.name}')
        if not self.is_playing:
            self.skip_event.set()

    def toggle_loop(self):
        self.is_looping = not self.is_looping
        logger.info(f"Looping set to {self.is_looping} in guild: {self._guild.name}")
        return self.is_looping

    async def stop(self):
        self.queue.clear()
        self.voice_client.stop()
        await self.voice_client.disconnect()
        self.player_task.cancel()
        logger.info(f"Stopped playback and disconnected from guild: {self._guild.name}")


# Helper function to get or create a MusicPlayer
def get_player(ctx):
    try:
        player = music_players[ctx.guild.id]
    except KeyError:
        player = MusicPlayer(ctx)
        music_players[ctx.guild.id] = player
    return player


# Commands


@bot.event
async def on_ready():
    logger.info(f"Logged in as {bot.user} (ID: {bot.user.id})")
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")


@bot.command(name="help")
async def help_command(ctx):
    help_text = """
**Music Bot Commands:**
`!join` - Joins your current voice channel.
`!play <song>` - Searches and plays a song from YouTube.
`!skip` - Skips the current song.
`!stop` - Stops playback and clears the queue.
`!queue` - Displays the current song queue.
`!loop` - Toggles looping the current song.
"""
    await ctx.send(help_text)


@bot.command(name="join")
async def join(ctx):
    if not ctx.author.voice:
        await ctx.send("You're not connected to a voice channel.")
        return
    channel = ctx.author.voice.channel
    if ctx.voice_client is not None:
        if ctx.voice_client.channel.id == channel.id:
            await ctx.send("I'm already in your voice channel.")
            return
        else:
            await ctx.voice_client.move_to(channel)
            await ctx.send(f"Moved to {channel}.")
            logger.info(f"Moved to voice channel: {channel} in guild: {ctx.guild.name}")
            return
    try:
        await channel.connect()
        await ctx.send(f"Joined {channel}.")
        logger.info(f"Joined voice channel: {channel} in guild: {ctx.guild.name}")
    except Exception as e:
        logger.error(f"Failed to join voice channel: {e}")
        await ctx.send("Failed to join voice channel.")


@bot.command(name="play")
async def play(ctx, *, query: str):
    if not ctx.author.voice:
        await ctx.send("You need to be in a voice channel to play music.")
        return
    channel = ctx.author.voice.channel
    player = get_player(ctx)

    if ctx.voice_client is None:
        try:
            player.voice_client = await channel.connect()
            logger.info(
                f"Connected to voice channel: {channel} in guild: {ctx.guild.name}"
            )
        except Exception as e:
            logger.error(f"Error connecting to voice channel: {e}")
            await ctx.send("Failed to connect to your voice channel.")
            return
    elif ctx.voice_client.channel != channel:
        try:
            await ctx.voice_client.move_to(channel)
            player.voice_client = ctx.voice_client
            logger.info(f"Moved to voice channel: {channel} in guild: {ctx.guild.name}")
        except Exception as e:
            logger.error(f"Error moving to voice channel: {e}")
            await ctx.send("Failed to move to your voice channel.")
            return

    await ctx.trigger_typing()

    try:
        info = ydl.extract_info(query, download=False)
        if "entries" in info:
            info = info["entries"][0]  # Take first entry from search
        url = info["url"]
        title = info.get("title", "Unknown Title")
        song = {"title": title, "url": url}
        player.add_to_queue(song)
        await ctx.send(f"**{title}** added to the queue.")
    except Exception as e:
        logger.error(f"Error extracting video info: {e}")
        await ctx.send("Couldn't find the song you requested.")
        return


@bot.command(name="skip")
async def skip(ctx):
    if not ctx.voice_client or not ctx.voice_client.is_connected():
        await ctx.send("I'm not connected to any voice channel.")
        return
    player = get_player(ctx)
    if not ctx.voice_client.is_playing():
        await ctx.send("Nothing is playing.")
        return
    ctx.voice_client.stop()
    await ctx.send("Skipped the current song.")
    logger.info(f"Skipped song in guild: {ctx.guild.name}")


@bot.command(name="stop")
async def stop(ctx):
    if not ctx.voice_client or not ctx.voice_client.is_connected():
        await ctx.send("I'm not connected to any voice channel.")
        return
    player = get_player(ctx)
    await player.stop()
    del music_players[ctx.guild.id]
    await ctx.send("Stopped playback and cleared the queue.")
    logger.info(f"Stopped playback and cleared queue in guild: {ctx.guild.name}")


@bot.command(name="queue")
async def queue_command(ctx):
    player = get_player(ctx)
    if not player.queue and not player.is_playing:
        await ctx.send("The queue is empty.")
        return
    embed = discord.Embed(title="Song Queue", color=discord.Color.blue())
    if player.current:
        embed.add_field(name="Now Playing", value=player.current["title"], inline=False)
    if player.queue:
        upcoming = list(player.queue)[:10]  # Show up to next 10 songs
        upcoming_str = "\n".join(
            [f"{idx + 1}. {song['title']}" for idx, song in enumerate(upcoming)]
        )
        embed.add_field(name="Up Next", value=upcoming_str, inline=False)
    await ctx.send(embed=embed)


@bot.command(name="loop")
async def loop_command(ctx):
    player = get_player(ctx)
    is_looping = player.toggle_loop()
    status = "enabled" if is_looping else "disabled"
    await ctx.send(f"Looping is now {status}.")
    logger.info(f"Looping {status} in guild: {ctx.guild.name}")


@play.before_invoke
@join.before_invoke
async def ensure_voice(ctx):
    if not ctx.author.voice:
        await ctx.send("You need to be connected to a voice channel.")
        raise commands.CommandError("Author not connected to a voice channel.")


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandError):
        await ctx.send(str(error))
        logger.warning(f"CommandError: {error}")
    else:
        await ctx.send("An unexpected error occurred.")
        logger.error(f"Unhandled error: {error}")


# Run the bot
if TOKEN is None:
    logger.critical("DISCORD_TOKEN not found in environment variables.")
    print("DISCORD_TOKEN not found. Please set it in the .env file.")
else:
    bot.run(TOKEN)
