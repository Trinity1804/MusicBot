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

Type `!loop on` or `!loop off` to turn the looping of the currently playing song on or off (looping is off by default)

Type `!skip` to skip the current song

Type `!stop` to exit the voice channel

Type `!pause` ro pause the currently playing song

Type `!resume` to resume the paused song

Type `!queue` to show the current song queue
