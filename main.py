import discord
from discord.ext import commands
import yt_dlp as youtube_dl
import asyncio
import os
from dotenv import load_dotenv, dotenv_values

load_dotenv()

token = os.getenv("BOT_TOKEN")

bot = commands.Bot(command_prefix="!", intents=discord.Intents.all())

# Queue to hold the songs, and a loop flag
songs_queue = []
is_looping = False
current_song = None

# YTDL options
ytdl_format_options = {
    "format": "bestaudio",
    "postprocessors": [
        {
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }
    ],
    "quiet": False,
    "no_warnings": True,
    "default_search": "auto",
    "source_address": "0.0.0.0",
}

ffmpeg_options = {
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    "options": "-vn",
}

ytdl = youtube_dl.YoutubeDL(ytdl_format_options)


def search(query):
    try:
        info = ytdl.extract_info(f"ytsearch:{query}", download=False)
        if "entries" in info and len(info["entries"]) > 0:
            video = info["entries"][0]
            return {
                "webpage_url": video["webpage_url"],
                "title": video["title"],
                "url": video["url"],
            }
        else:
            print("No entries found.")
        return None
    except youtube_dl.DownloadError as e:
        print(f"Download Error: {e}")
        return None
    except Exception as e:
        print(f"Unexpected error: {e}")
        return None


async def play_next(ctx):
    global is_looping, current_song
    if ctx.voice_client is None:
        await ctx.invoke(join)

    if is_looping and current_song:
        # Restart the same song
        source = discord.FFmpegPCMAudio(current_song["url"], **ffmpeg_options)
        ctx.voice_client.play(
            discord.PCMVolumeTransformer(source),
            after=lambda e: asyncio.run_coroutine_threadsafe(
                play_next(ctx), bot.loop
            ).result(),
        )
    elif songs_queue:
        current_song = songs_queue.pop(0)
        source = discord.FFmpegPCMAudio(current_song["url"], **ffmpeg_options)
        ctx.voice_client.play(
            discord.PCMVolumeTransformer(source),
            after=lambda e: asyncio.run_coroutine_threadsafe(
                play_next(ctx), bot.loop
            ).result(),
        )
        await ctx.send(f"Now playing: {current_song['title']}")
    else:
        current_song = None
        await ctx.voice_client.disconnect()


@bot.event
async def on_ready():
    print("Bot is ready!")


@bot.command(name="join", help="Joins the voice channel you are in.")
async def join(ctx):
    if not ctx.author.voice:
        await ctx.send("You are not connected to a voice channel.")
        return

    channel = ctx.author.voice.channel
    if ctx.voice_client is not None:
        await ctx.voice_client.move_to(channel)
    else:
        await channel.connect()


@bot.command(name="play", help="Plays a song.")
async def play(ctx, *, query):
    global current_song
    song = search(query)
    if song:
        songs_queue.append(song)
        await ctx.send(f"Added to queue: {song['title']}")

        # If no song is currently playing, start playing the newly added song
        if not ctx.voice_client.is_playing():
            current_song = songs_queue.pop(0)
            await play_next(ctx)
    else:
        await ctx.send("Could not find the song.")


@bot.command(name="skip", help="Skips the current song.")
async def skip(ctx):
    if ctx.voice_client.is_playing():
        ctx.voice_client.stop()


@bot.command(name="stop", help="Stops the bot and clears the queue.")
async def stop(ctx):
    global is_looping, current_song
    songs_queue.clear()
    is_looping = False
    current_song = None
    if ctx.voice_client.is_playing():
        ctx.voice_client.stop()
    await ctx.voice_client.disconnect()


@bot.command(name="queue", help="Shows the current song queue.")
async def queue(ctx):
    if not songs_queue:
        await ctx.send("The queue is empty.")
    else:
        queue_list = "\n".join(song["title"] for song in songs_queue)
        await ctx.send(f"Current queue:\n{queue_list}")


@bot.command(name="loop", help="Toggles looping the current song.")
async def loop(ctx):
    global is_looping
    is_looping = not is_looping
    await ctx.send(f"Looping is now {'enabled' if is_looping else 'disabled'}")


bot.run(token)
