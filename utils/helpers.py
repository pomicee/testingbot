import re
import time
import discord

def format_time(seconds):
    """
    Format seconds into a time string (HH:MM:SS).
    
    Args:
        seconds: Time in seconds
        
    Returns:
        Formatted time string
    """
    hours, remainder = divmod(int(seconds), 3600)
    minutes, seconds = divmod(remainder, 60)
    
    if hours:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    else:
        return f"{minutes}:{seconds:02d}"

def format_uptime(start_time):
    """
    Format uptime from a start timestamp.
    
    Args:
        start_time: Start time timestamp
        
    Returns:
        Formatted uptime string
    """
    uptime = time.time() - start_time
    d, remainder = divmod(int(uptime), 86400)
    h, remainder = divmod(remainder, 3600)
    m, s = divmod(remainder, 60)
    
    parts = []
    if d > 0:
        parts.append(f"{d} day{'s' if d != 1 else ''}")
    if h > 0:
        parts.append(f"{h} hour{'s' if h != 1 else ''}")
    if m > 0:
        parts.append(f"{m} minute{'s' if m != 1 else ''}")
    if s > 0 or not parts:
        parts.append(f"{s} second{'s' if s != 1 else ''}")
    
    return ", ".join(parts)

def is_url(string):
    """
    Check if a string is a URL.
    
    Args:
        string: String to check
        
    Returns:
        True if the string is a URL, False otherwise
    """
    url_regex = re.compile(
        r'^(?:http|https)://'  
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|'  
        r'localhost|' 
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})' 
        r'(?::\d+)?' 
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    
    return bool(url_regex.match(string))

async def ensure_voice(ctx):
    """
    Ensure the bot and user are in a voice channel.
    
    Args:
        ctx: Command context
        
    Returns:
        True if the check passes
        
    Raises:
        commands.CommandError: If the check fails
    """
    if not ctx.author.voice:
        raise discord.app_commands.AppCommandError("You must be connected to a voice channel.")
    
    if ctx.guild.me.voice and ctx.guild.me.voice.channel != ctx.author.voice.channel:
        raise discord.app_commands.AppCommandError("I'm already connected to another voice channel.")
    
    return True

def get_track_source_emoji(track):
    """
    Get an emoji representing the source of a track.
    
    Args:
        track: The track
        
    Returns:
        Emoji string
    """
    source_name = track.info.get("sourceName", "").lower()
    
    if "youtube" in source_name:
        return "🎬"
    elif "soundcloud" in source_name:
        return "☁️"
    elif "spotify" in source_name:
        return "🟢"
    elif "bandcamp" in source_name:
        return "🎵"
    elif "twitch" in source_name:
        return "🟣"
    elif "vimeo" in source_name:
        return "🎞️"
    else:
        return "🎵"
