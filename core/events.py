import logging
import discord
from discord.ext import commands

from utils.embeds import now_playing_embed, error_embed

logger = logging.getLogger(__name__)

class EventHandler:
    """Handler for various bot events."""
    
    def __init__(self, bot):
        self.bot = bot
        
        self.register_events()
        
    def register_events(self):
        """Register all event handlers with the bot."""
        self.bot.add_listener(self.on_pomice_track_end, 'on_pomice_track_end')
        self.bot.add_listener(self.on_pomice_track_exception, 'on_pomice_track_exception')
        self.bot.add_listener(self.on_pomice_track_stuck, 'on_pomice_track_stuck')
        self.bot.add_listener(self.on_voice_state_update, 'on_voice_state_update')
        
        logger.info("Registered event handlers")
    
    async def on_pomice_track_end(self, player, track, _):
        """
        Event fired when a track ends.
        
        Args:
            player: The player instance
            track: The track that ended
            _: The reason the track ended
        """
        if player.loop:
            await player.queue.put(track)
        
        await self.process_next_track(player)
    
    async def on_pomice_track_exception(self, player, track, error):
        """
        Event fired when a track throws an exception.
        
        Args:
            player: The player instance
            track: The track that threw an exception
            error: The exception thrown
        """
        logger.error(f"Error playing track {track.title}: {error}")
        
        if player.bound_channel:
            await player.bound_channel.send(
                embed=error_embed(f"Error playing track: {error}")
            )
        
        await self.process_next_track(player)
    
    async def on_pomice_track_stuck(self, player, track, threshold):
        """
        Event fired when a track gets stuck.
        
        Args:
            player: The player instance
            track: The track that got stuck
            threshold: The threshold in milliseconds
        """
        logger.warning(f"Track {track.title} got stuck (threshold: {threshold}ms)")
        
        if player.bound_channel:
            await player.bound_channel.send(
                embed=error_embed(f"The track got stuck. Skipping to the next track.")
            )
        
        await self.process_next_track(player)
    
    async def on_voice_state_update(self, member, before, after):
        """
        Event fired when a member's voice state changes.
        
        Args:
            member: The member whose voice state changed
            before: The voice state before the change
            after: The voice state after the change
        """
        if member.id != self.bot.user.id:
            return
        
        if before.channel and not after.channel:
            player = self.bot.node.get_player(member.guild.id)
            if player:
                await player.teardown()
                logger.info(f"Bot was disconnected from voice in {member.guild.name}")
    
    async def process_next_track(self, player):
        """
        Process the next track in the queue.
        
        Args:
            player: The player instance
        """
        if player.queue.empty():
            return
        
        if player.waiting:
            return
            
        player.waiting = True
        
        try:
            track = await player.queue.get()
            
            ctx = None
            if player.message:
                ctx = await self.bot.get_context(player.message)
            
            await player.play(track)
            
            if player.bound_channel and ctx:
                embed = now_playing_embed(track, ctx.author)
                await player.bound_channel.send(embed=embed)
        except Exception as e:
            logger.error(f"Error processing next track: {e}")
            if player.bound_channel:
                await player.bound_channel.send(
                    embed=error_embed(f"Error playing next track: {e}")
                )
        finally:
            player.waiting = False
