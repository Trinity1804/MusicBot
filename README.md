# MusicBot
A simple discord bot for playing music in voice channels, written in python

## Requirements
- `pycord`
- `yt_dlp`
- `python-dotenv` (optional): You can choose to include the discord bot token in the `main.py` file instead of an ENV file, although it is not recommended
- `ffmpeg`

## Usage
Type `!join` for the bot to connect to your voice channel

Type `!play [video_url]` for the bot to play music from a YouTube URL

Type `!play [keyword]` for the bot to play music from the most relevant YouTube video based on the keyword provided

Type `!loop` to toggle looping of the currently playing song (looping is off by default)

Type `!skip` to skip the current song

Type `!stop` to exit the voice channel

Type `!queue` to show the current song queue
