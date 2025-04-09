import discord
import pomice
import logging
import asyncio
import random
from discord.ext import commands
from discord import app_commands

from core.player import MusicPlayer
from utils.embeds import (
    success_embed, error_embed, music_embed, 
    queue_embed, now_playing_embed
)
from utils.helpers import ensure_voice, is_url, format_time

logger = logging.getLogger(__name__)

class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.pomice = pomice.NodePool()
        self.looping = {}
        bot.loop.create_task(self.start_nodes())

    async def start_nodes(self):
        await self.bot.wait_until_ready()
        
        try:
            self.bot.node = await self.pomice.create_node(
                bot=self.bot,
                host=self.bot.config.LAVALINK["host"],
                port=self.bot.config.LAVALINK["port"],
                password=self.bot.config.LAVALINK["password"],
                identifier=self.bot.config.LAVALINK["identifier"],
                secure=self.bot.config.LAVALINK["secure"]
            )
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
                
                self.looping[ctx.guild.id] = False
        
        return player

    @commands.hybrid_group(name="queue", description="Manage the music queue")
    async def queue_cmd(self, ctx):
        if ctx.invoked_subcommand is None:
            await self.queue_view(ctx)

    @queue_cmd.command(name="view", description="View the current queue")
    async def queue_view(self, ctx, page: int = 1):
        player = await self.get_player(ctx, connect=False)
        embed = queue_embed(player, player.track, page)
        await ctx.send(embed=embed)

    @queue_cmd.command(name="clear", description="Clear the queue")
    async def queue_clear(self, ctx):
        player = await self.get_player(ctx, connect=False)
        await player.clear_queue()
        await ctx.send(embed=success_embed("The music queue has been cleared."))

    @queue_cmd.command(name="shuffle", description="Shuffle the queue")
    async def queue_shuffle(self, ctx):
        player = await self.get_player(ctx, connect=False)
        
        if player.queue.empty():
            await ctx.send(embed=error_embed("The queue is empty."))
            return
        
        queue_items = player.queue_list
        random.shuffle(queue_items)
        
        player.queue = asyncio.Queue()
        for item in queue_items:
            await player.queue.put(item)
        
        await ctx.send(embed=success_embed("The music queue has been shuffled."))

    @queue_cmd.command(name="remove", description="Remove a track from the queue")
    async def queue_remove(self, ctx, position: int):
        player = await self.get_player(ctx, connect=False)
        queue_items = player.queue_list
        
        if not queue_items or position < 1 or position > len(queue_items):
            await ctx.send(embed=error_embed("Invalid position."))
            return
        
        removed_track = queue_items.pop(position - 1)
        
        player.queue = asyncio.Queue()
        for track in queue_items:
            await player.queue.put(track)
        
        await ctx.send(embed=success_embed(f"Removed **{removed_track.title}** from the queue."))

    @queue_cmd.command(name="move", description="Move a track in the queue")
    async def queue_move(self, ctx, position: int, new_position: int):
        player = await self.get_player(ctx, connect=False)
        queue_items = player.queue_list
        
        if not queue_items or position < 1 or position > len(queue_items) or new_position < 1 or new_position > len(queue_items):
            await ctx.send(embed=error_embed("Invalid positions."))
            return
        
        track = queue_items.pop(position - 1)
        queue_items.insert(new_position - 1, track)
        
        player.queue = asyncio.Queue()
        for item in queue_items:
            await player.queue.put(item)
        
        await ctx.send(embed=success_embed(f"Moved **{track.title}** to position {new_position}."))

    @commands.hybrid_command(name="play", description="Play a track or playlist")
    async def play(self, ctx, *, query: str):
        await ctx.defer()
        player = await self.get_player(ctx)
        
        if not query:
            if player.is_paused:
                await player.set_pause(False)
                await ctx.send(embed=success_embed("Resumed playback."))
                return
            else:
                await ctx.send(embed=error_embed("Please provide a search query or URL."))
                return
        
        search_query = query
        if not is_url(query):
            search_query = f"ytsearch:{query}"
        
        try:
            result = await player.node.get_tracks(query=search_query, ctx=ctx)
        except Exception as e:
            logger.error(f"Error searching for tracks: {e}")
            await ctx.send(embed=error_embed("An error occurred while searching. Please try again."))
            return
            
        if not result:
            await ctx.send(embed=error_embed("No results found."))
            return

        player.message = ctx.message
        
        if isinstance(result, pomice.Playlist):
            tracks = result.tracks
            
            for track in tracks:
                await player.insert(track)
                
            await ctx.send(
                embed=success_embed(f"Added **{len(tracks)}** tracks from playlist **{result.name}** to the queue.")
            )
        else:
            track = result[0]
            await player.insert(track)
            
            position = player.queue.qsize()
            
            if player.is_playing:
                await ctx.send(
                    embed=success_embed(
                        f"Added **[{track.title}]({track.uri})** to position #{position} in the queue."
                    )
                )
            else:
                await ctx.send(
                    embed=success_embed(
                        f"Added **[{track.title}]({track.uri})** to the queue."
                    )
                )

        if not player.is_playing and not player.waiting:
            await self.process_next_track(player, ctx.author)

    @commands.hybrid_command(name="playnext", description="Add a track to the top of the queue")
    async def playnext(self, ctx, *, query: str):
        await ctx.defer()
        player = await self.get_player(ctx)
        
        search_query = query
        if not is_url(query):
            search_query = f"ytsearch:{query}"
        
        try:
            result = await player.node.get_tracks(query=search_query, ctx=ctx)
        except Exception as e:
            logger.error(f"Error searching for tracks: {e}")
            await ctx.send(embed=error_embed("An error occurred while searching. Please try again."))
            return
            
        if not result:
            await ctx.send(embed=error_embed("No results found."))
            return

        player.message = ctx.message
        
        if isinstance(result, pomice.Playlist):
            tracks = result.tracks
            
            current_queue = player.queue_list
            player.queue = asyncio.Queue()
            
            for track in tracks:
                await player.queue.put(track)
                
            for track in current_queue:
                await player.queue.put(track)
                
            await ctx.send(
                embed=success_embed(f"Added **{len(tracks)}** tracks from playlist **{result.name}** to the front of the queue.")
            )
        else:
            track = result[0]
            
            current_queue = player.queue_list
            player.queue = asyncio.Queue()
            
            await player.queue.put(track)
            
            for item in current_queue:
                await player.queue.put(item)
                
            await ctx.send(
                embed=success_embed(
                    f"Added **[{track.title}]({track.uri})** to the front of the queue."
                )
            )

        if not player.is_playing and not player.waiting:
            await self.process_next_track(player, ctx.author)

    @commands.hybrid_command(name="pause", description="Pause the current track")
    async def pause(self, ctx):
        player = await self.get_player(ctx, connect=False)
        
        if not player.is_playing:
            await ctx.send(embed=error_embed("Nothing is playing right now."))
            return
            
        if player.is_paused:
            await ctx.send(embed=error_embed("The player is already paused."))
            return
            
        await player.set_pause(True)
        await ctx.send(embed=success_embed("Paused the player."))

    @commands.hybrid_command(name="resume", description="Resume the current track")
    async def resume(self, ctx):
        player = await self.get_player(ctx, connect=False)
        
        if not player.is_playing:
            await ctx.send(embed=error_embed("Nothing is playing right now."))
            return
            
        if not player.is_paused:
            await ctx.send(embed=error_embed("The player is not paused."))
            return
            
        await player.set_pause(False)
        await ctx.send(embed=success_embed("Resumed the player."))

    @commands.hybrid_command(name="skip", description="Skip the current track")
    async def skip(self, ctx):
        player = await self.get_player(ctx, connect=False)
        
        if not player.is_playing:
            await ctx.send(embed=error_embed("Nothing is playing right now."))
            return
            
        await player.stop()
        await ctx.send(embed=success_embed("Skipped the current track."))

    @commands.hybrid_command(name="stop", description="Stop playback and clear the queue")
    async def stop(self, ctx):
        player = await self.get_player(ctx, connect=False)
        
        player.queue = asyncio.Queue()
        await player.stop()
        
        await ctx.send(embed=success_embed("Stopped playback and cleared the queue."))

    @commands.hybrid_command(name="seek", description="Seek to a position in the current track")
    async def seek(self, ctx, position: str):
        player = await self.get_player(ctx, connect=False)
        
        if not player.is_playing:
            await ctx.send(embed=error_embed("Nothing is playing right now."))
            return
            
        if not player.track.is_seekable:
            await ctx.send(embed=error_embed("This track cannot be seeked."))
            return
            
        seconds = 0
        
        if ":" in position:
            parts = position.split(":")
            if len(parts) == 2:
                seconds = int(parts[0]) * 60 + int(parts[1])
            elif len(parts) == 3:
                seconds = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
        else:
            try:
                seconds = int(position)
            except ValueError:
                await ctx.send(embed=error_embed("Invalid position format. Use seconds or MM:SS or HH:MM:SS."))
                return
                
        milliseconds = seconds * 1000
        
        track_length = player.track.length
        if milliseconds > track_length:
            await ctx.send(embed=error_embed(f"The track is only {format_time(track_length/1000)} long."))
            return
            
        await player.seek(milliseconds)
        await ctx.send(embed=success_embed(f"Seeked to {format_time(seconds)}."))

    @commands.hybrid_command(name="volume", description="Set the player volume")
    async def volume(self, ctx, volume: int):
        player = await self.get_player(ctx, connect=False)
        
        if volume < 0 or volume > 150:
            await ctx.send(embed=error_embed("Volume must be between 0 and 150."))
            return
            
        await player.set_volume(volume)
        await ctx.send(embed=success_embed(f"Set volume to **{volume}%**."))

    @commands.hybrid_command(name="now", description="Show the currently playing track")
    async def now(self, ctx):
        player = await self.get_player(ctx, connect=False)
        
        if not player.is_playing:
            await ctx.send(embed=error_embed("Nothing is playing right now."))
            return
            
        embed = now_playing_embed(player.track, ctx.author)
        
        position = player.position
        duration = player.track.length
        
        bar_length = 20
        progress = int(bar_length * (position / duration)) if duration > 0 else 0
        
        progress_bar = "▬" * progress + "🔘" + "▬" * (bar_length - progress - 1)
        
        current_position = format_time(position / 1000)
        total_duration = format_time(duration / 1000)
        
        embed.add_field(
            name="Progress",
            value=f"{current_position} {progress_bar} {total_duration}",
            inline=False
        )
        
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="loop", description="Toggle track looping")
    async def loop(self, ctx):
        player = await self.get_player(ctx, connect=False)
        guild_id = ctx.guild.id
        
        self.looping[guild_id] = not self.looping.get(guild_id, False)
        player.loop = self.looping[guild_id]
        
        status = "enabled" if self.looping[guild_id] else "disabled"
        await ctx.send(embed=success_embed(f"Track looping {status}."))

    @commands.hybrid_command(name="disconnect", description="Disconnect from the voice channel")
    async def disconnect(self, ctx):
        player = await self.get_player(ctx, connect=False)
        
        await player.teardown()
        self.looping[ctx.guild.id] = False
        
        await ctx.send(embed=success_embed("Disconnected from the voice channel."))

    @commands.hybrid_command(name="lyrics", description="Search for lyrics of the current or specified song")
    async def lyrics(self, ctx, *, query: str = None):
        player = await self.get_player(ctx, connect=False) if not query else None
        
        if not query and not player.is_playing:
            await ctx.send(embed=error_embed("Nothing is playing and no search query was provided."))
            return
            
        search_query = query if query else player.track.title
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"https://api.lyrics.ovh/v1/{search_query.split(' - ')[0]}/{search_query.split(' - ')[1] if ' - ' in search_query else search_query}",
                    timeout=10
                ) as response:
                    if response.status != 200:
                        await ctx.send(embed=error_embed(f"No lyrics found for {search_query}."))
                        return
                        
                    data = await response.json()
                    lyrics = data["lyrics"]
                    
                    if len(lyrics) > 4000:
                        lyrics = lyrics[:4000] + "..."
                        
                    embed = music_embed(
                        title=f"Lyrics for {search_query}",
                        description=lyrics
                    )
                    
                    await ctx.send(embed=embed)
        except Exception as e:
            logger.error(f"Error fetching lyrics: {e}")
            await ctx.send(embed=error_embed(f"An error occurred while fetching lyrics for {search_query}."))

    async def process_next_track(self, player, user):
        if player.queue.empty():
            return
            
        if player.waiting:
            return
            
        player.waiting = True
        
        try:
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
        guild_id = int(player.guild_id)
        
        if self.looping.get(guild_id, False):
            await player.queue.put(track)
            
        ctx = None
        if player.message:
            ctx = await self.bot.get_context(player.message)
            
        if ctx:
            await self.process_next_track(player, ctx.author)

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
                await player.teardown()

async def setup(bot):
    await bot.add_cog(Music(bot))
