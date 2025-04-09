import discord

def base_embed(title=None, description=None):
    """Create a base embed with consistent styling."""
    embed = discord.Embed(
        title=title,
        description=description,
        color=0x808080  
    )
    return embed

def success_embed(description):
    """Create a success embed."""
    embed = discord.Embed(
        title="Success",
        description=description,
        color=0x2ecc71  
    )
    return embed

def error_embed(description):
    """Create an error embed."""
    embed = discord.Embed(
        title="Error",
        description=description,
        color=0xe74c3c 
    )
    return embed

def music_embed(title=None, description=None):
    """Create a music-specific embed."""
    embed = discord.Embed(
        title=title,
        description=description,
        color=0x3498db  
    )
    return embed

def now_playing_embed(track, requester):
    """Create an embed for the now playing message."""
    duration_ms = track.info.get('length', 0)
    duration_sec = duration_ms // 1000
    minutes = duration_sec // 60
    seconds = duration_sec % 60
    
    embed = discord.Embed(
        title="Now Playing",
        description=f"[{track.title}]({track.uri})",
        color=0x3498db
    )
    if track.info.get('author'):
        embed.add_field(name="Artist", value=track.info.get('author'), inline=True)
    embed.add_field(name="Duration", value=f"{minutes}:{seconds:02d}", inline=True)
    
    embed.set_footer(
        text=f"Requested by: {requester.name}",
        icon_url=requester.avatar.url if requester.avatar else None
    )
    
    if track.info.get('thumbnail'):
        embed.set_thumbnail(url=track.info.get('thumbnail'))
    
    return embed

def queue_embed(player, current_track=None, page=1, items_per_page=10):
    """Create an embed for the queue."""
    queue_items = player.queue_list
    total_pages = (len(queue_items) + items_per_page - 1) // items_per_page
    
    page = max(1, min(page, total_pages or 1))
    
    start_idx = (page - 1) * items_per_page
    end_idx = min(start_idx + items_per_page, len(queue_items))
    
    embed = discord.Embed(
        title="Music Queue",
        color=0x3498db
    )
    
    if current_track:
        embed.add_field(
            name="Now Playing",
            value=f"[{current_track.title}]({current_track.uri})",
            inline=False
        )
    if not queue_items:
        embed.description = "The queue is currently empty."
    else:
        queue_list = []
        for i, track in enumerate(queue_items[start_idx:end_idx], start=start_idx + 1):
            queue_list.append(f"{i}. [{track.title}]({track.uri})")
        
        embed.description = "\n".join(queue_list)
        
        if total_pages > 1:
            embed.set_footer(text=f"Page {page}/{total_pages}")
    
    return embed
