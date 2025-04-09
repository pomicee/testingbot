import discord
import pomice
import logging
import random
import asyncio
from discord.ext import commands
from discord import app_commands

from core.player import MusicPlayer
from utils.embeds import (
    success_embed, error_embed, music_embed, 
    queue_embed, now_playing_embed
)
from utils.helpers import is_url, format_time
import aiohttp

logger = logging.getLogger(__name__)
def ensure_voice(check_playing=False):
    async def predicate(ctx):
        if not ctx.author.voice:
            await ctx.send(embed=error_embed("You must be connected to a voice channel to use this command."))
            return False
            
        if check_playing:
            player = ctx.bot.node.get_player(ctx.guild.id)
            if not player or not player.is_playing and not player.is_paused:
                await ctx.send(embed=error_embed("Nothing is currently playing."))
                return False
                
        return True
    return commands.check(predicate)

class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.pomice = pomice.NodePool()
        self.looping = {}
        self.node_ready = False
        self.player_guilds = {}

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.node_ready:
            await self.start_nodes()

    async def start_nodes(self):
        try:
            self.bot.node = await self.pomice.create_node(
                bot=self.bot,
                host="lava-v4.ajieblogs.eu.org",
                port=80,
                password="https://dsc.gg/ajidevserver",
                identifier="MAIN",
            )
            self.node_ready = True
            logger.info("Lavalink node is ready!")
        except Exception as error:
            logger.error(f"Failed to initialize Lavalink node: {error}")

    async def get_player(self, ctx, *, connect=True):
        if not hasattr(self.bot, "node") or self.bot.node is None:
            raise commands.CommandError("Music system is not ready. Please try again later.")
        
        if not ctx.author.voice:
            raise commands.CommandError("You must be connected to a voice channel.")
        
        if ctx.guild.me.voice and ctx.guild.me.voice.channel != ctx.author.voice.channel:
            raise commands.CommandError("I'm already connected to another voice channel.")
        
        player = self.bot.node.get_player(ctx.guild.id)
        
        if player is None or not ctx.guild.me.voice:
            if not connect:
                raise commands.CommandError("I'm not connected to a voice channel.")
            else:
                await ctx.author.voice.channel.connect(cls=MusicPlayer, self_deaf=True)
                player = self.bot.node.get_player(ctx.guild.id)
                
                player.bound_channel = ctx.channel
                await player.set_volume(self.bot.config.DEFAULT_VOLUME)
                player.voice_channel = ctx.author.voice.channel.id
                player.guild_id = ctx.guild.id 
                
                self.player_guilds[player] = ctx.guild.id
                self.looping[ctx.guild.id] = False
        
        return player

    @commands.hybrid_command(name="play", description="Play a song or add it to the queue")
    @app_commands.describe(query="Song name or URL to play")
    @ensure_voice()
    async def play(self, ctx, *, query: str):
        """Play a song from YouTube, Spotify, or other supported platforms."""
        await ctx.defer()
        
        player = await self.get_player(ctx)
        player.message = ctx.message
        
        if not query:
            if player.is_paused:
                await player.resume()
                return await ctx.send(embed=success_embed("Resumed playback"))
            return await ctx.send(embed=error_embed("Please provide a song name or URL"))
            
        try:
            if not is_url(query):
                query = f"ytsearch:{query}"
                
            results = await player.get_tracks(query)
            
            if not results:
                return await ctx.send(embed=error_embed(f"No results found for: {query}"))
            if hasattr(results, 'tracks') and results.tracks:
                tracks = results.tracks
                playlist_name = getattr(results, 'name', 'Playlist')
                
                for track in tracks:
                    track.requester = ctx.author
                    await player.queue.put(track)
                    
                await ctx.send(embed=success_embed(f"Added {len(tracks)} tracks from playlist: **{playlist_name}**"))
            else:
                track = results[0]
                track.requester = ctx.author
                await player.queue.put(track)
                await ctx.send(embed=music_embed(track, ctx.author))
                    
            if not player.is_playing and not player.waiting:
                await self.process_next_track(player, ctx.author)
                
        except Exception as e:
            logger.error(f"Error in play command: {e}")
            await ctx.send(embed=error_embed(f"An error occurred: {str(e)}"))

    @commands.hybrid_command(name="queue", description="Display the music queue")
    @ensure_voice()
    async def queue(self, ctx):
        """Display the current music queue."""
        player = await self.get_player(ctx, connect=False)
        
        if player.queue.empty() and not player.is_playing:
            return await ctx.send(embed=error_embed("The queue is empty and nothing is playing."))
            
        await ctx.send(embed=queue_embed(player, ctx.guild))

    @commands.hybrid_command(name="pause", description="Pause the current song")
    @ensure_voice()
    async def pause(self, ctx):
        """Pause the currently playing song."""
        player = await self.get_player(ctx, connect=False)
        
        if not player.is_playing:
            return await ctx.send(embed=error_embed("Nothing is playing."))
            
        if player.is_paused:
            return await ctx.send(embed=error_embed("The player is already paused."))
            
        await player.pause()
        await ctx.send(embed=success_embed("Paused playback"))

    @commands.hybrid_command(name="resume", description="Resume the current song")
    @ensure_voice()
    async def resume(self, ctx):
        """Resume the currently paused song."""
        player = await self.get_player(ctx, connect=False)
        
        if not player.is_playing and not player.is_paused:
            return await ctx.send(embed=error_embed("Nothing is playing."))
            
        if not player.is_paused:
            return await ctx.send(embed=error_embed("The player is not paused."))
            
        await player.resume()
        await ctx.send(embed=success_embed("Resumed playback"))

    @commands.hybrid_command(name="volume", description="Change the volume (0-100)")
    @app_commands.describe(volume="Volume level (0-100)")
    @ensure_voice()
    async def volume(self, ctx, volume: int = None):
        """Change the volume of the player (0-100)."""
        player = await self.get_player(ctx, connect=False)
        
        if volume is None:
            return await ctx.send(embed=success_embed(f"Current volume: **{player.volume}%**"))
            
        if not 0 <= volume <= 100:
            return await ctx.send(embed=error_embed("Volume must be between 0 and 100"))
            
        await player.set_volume(volume)
        await ctx.send(embed=success_embed(f"Set volume to **{volume}%**"))
    
    @commands.hybrid_command(name="skip", description="Skip the current song")
    @ensure_voice()
    async def skip(self, ctx):
        """Skip the currently playing song."""
        player = await self.get_player(ctx, connect=False)
        
        if not player.is_playing:
            return await ctx.send(embed=error_embed("Nothing is playing."))
            
        await player.stop()
        await ctx.send(embed=success_embed("Skipped the current track"))

    @commands.hybrid_command(name="stop", description="Stop playback and clear the queue")
    @ensure_voice()
    async def stop(self, ctx):
        """Stop playback and clear the queue."""
        player = await self.get_player(ctx, connect=False)
        
        player.queue.clear()
        await player.stop()
        await ctx.send(embed=success_embed("Stopped playback and cleared the queue"))

    @commands.hybrid_command(name="nowplaying", aliases=["np"], description="Show the currently playing song")
    @ensure_voice()
    async def nowplaying(self, ctx):
        """Display information about the currently playing song."""
        player = await self.get_player(ctx, connect=False)
        
        if not player.is_playing:
            return await ctx.send(embed=error_embed("Nothing is playing."))
            
        await ctx.send(embed=now_playing_embed(player.current, player.current.requester or ctx.author))

    @commands.hybrid_command(name="shuffle", description="Shuffle the music queue")
    @ensure_voice()
    async def shuffle(self, ctx):
        """Shuffle the songs in the queue."""
        player = await self.get_player(ctx, connect=False)
        
        if player.queue.empty():
            return await ctx.send(embed=error_embed("The queue is empty."))
        queue_list = list(player.queue._queue)
        random.shuffle(queue_list)
        player.queue.clear()
        for track in queue_list:
            await player.queue.put(track)
            
        await ctx.send(embed=success_embed(f"Shuffled **{len(queue_list)}** tracks in the queue"))

    @commands.hybrid_command(name="loop", description="Toggle loop mode")
    @ensure_voice()
    async def loop(self, ctx):
        """Toggle song looping on or off."""
        player = await self.get_player(ctx, connect=False)
        
        if not ctx.guild.id in self.looping:
            self.looping[ctx.guild.id] = False
            
        self.looping[ctx.guild.id] = not self.looping[ctx.guild.id]
        status = "enabled" if self.looping[ctx.guild.id] else "disabled"
        
        await ctx.send(embed=success_embed(f"Loop mode is now **{status}**"))
    
    @commands.hybrid_command(name="disconnect", aliases=["dc", "leave"], description="Disconnect the bot from voice")
    @ensure_voice()
    async def disconnect(self, ctx):
        """Disconnect the bot from the voice channel."""
        player = await self.get_player(ctx, connect=False)
        
        await player.teardown()
        if player in self.player_guilds:
            del self.player_guilds[player]
            
        await ctx.send(embed=success_embed("Disconnected from voice channel"))

    @commands.hybrid_command(name="seek", description="Seek to a position in the current song")
    @app_commands.describe(position="Position to seek to (in seconds)")
    @ensure_voice()
    async def seek(self, ctx, position: int):
        """Seek to a specific position in the current song (in seconds)."""
        player = await self.get_player(ctx, connect=False)
        
        if not player.is_playing:
            return await ctx.send(embed=error_embed("Nothing is playing."))
            
        if not 0 <= position <= (player.current.length / 1000):
            return await ctx.send(embed=error_embed(f"Position must be between 0 and {int(player.current.length / 1000)} seconds"))
            
        position_ms = position * 1000
        await player.seek(position_ms)
        
        formatted_position = format_time(position_ms)
        await ctx.send(embed=success_embed(f"Seeked to **{formatted_position}**"))

    async def process_next_track(self, player, user):
        if player.is_playing or player.waiting:
            return
            
        player.waiting = True
        
        try:
            if player.queue.empty():
                player.waiting = False
                return
                
            track = await player.queue.get()
            await player.play(track)
            
            if player.bound_channel:
                embed = now_playing_embed(track, user)
                await player.bound_channel.send(embed=embed)
        except Exception as e:
            logger.error(f"Error processing next track: {e}")
            if player.bound_channel:
                await player.bound_channel.send(embed=error_embed(f"An error occurred while playing the next track: {e}"))
        finally:
            player.waiting = False

    @commands.Cog.listener()
    async def on_pomice_track_end(self, player, track, reason):
        guild_id = None
        
        if player in self.player_guilds:
            guild_id = self.player_guilds[player]
        elif hasattr(player, 'guild_id'):
            guild_id = player.guild_id
            
        if guild_id is None:
            logger.warning("Could not determine guild_id in on_pomice_track_end")
            return
           
        if reason == "FINISHED":
            if self.looping.get(guild_id, False):
                await player.queue.put(track)
            
            user = None
            ctx = None
            if player.message:
                ctx = await self.bot.get_context(player.message)
                if ctx:
                    user = ctx.author
            
            if not user and hasattr(player, 'bound_channel'):
                user = self.bot.user
                
            await self.process_next_track(player, user or self.bot.user)

    @commands.Cog.listener()
    async def on_pomice_track_stuck(self, player, track, threshold):
        if player.bound_channel:
            await player.bound_channel.send(embed=error_embed("The track got stuck. Skipping to the next track."))
        await player.stop()

    @commands.Cog.listener()
    async def on_pomice_track_exception(self, player, track, error):
        if player.bound_channel:
            await player.bound_channel.send(embed=error_embed(f"An error occurred while playing the track: {error}"))
        await player.stop()

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if member.id != self.bot.user.id:
            return
            
        if before.channel and not after.channel:
            player = self.bot.node.get_player(member.guild.id)
            if player:
                if player in self.player_guilds:
                    del self.player_guilds[player]
                await player.teardown()

async def setup(bot):
    await bot.add_cog(Music(bot))
