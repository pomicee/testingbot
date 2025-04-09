import asyncio
import logging
import aiohttp
import discord
import pomice
import random
import requests

from discord.ext import commands

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Player(pomice.Player):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bound_channel = None
        self.message = None
        self.track = None
        self.queue = asyncio.Queue()
        self.waiting = False
        self.loop = False
        self.voice_channel = None
        
    async def play(self, track):
        self.track = track
        await super().play(track)

    async def insert(self, track, filter=True):
        if filter and track.info.get("sourceName", "YouTube") == "youtube":
            try:
                response = requests.get(
                    "https://metadata-filter.vercel.app/api/youtube", 
                    params=dict(track=track.title)
                )
                data = response.json()

                if data.get("status") == "success":
                    track.title = data["data"].get("track")
            except Exception as e:
                logger.error(f"Error filtering track metadata: {e}")
                
        await self.queue.put(track)
        return track

class Music(commands.Cog, name="Music"):
    def __init__(self, bot):
        self.bot = bot
        self.pomice = pomice.NodePool()
        self.looping = False
        bot.loop.create_task(self.start_nodes())

    async def start_nodes(self):
        await self.bot.wait_until_ready()
        try:
            self.bot.node = await self.pomice.create_node(
                bot=self.bot,
                host="host",
                port=443,
                password="password",
                identifier="MAIN",
                secure=False
            )
            logger.info("Node is ready!")
        except Exception as error:
            logger.error(f"Couldn't initiate Lavalink: {error}")

    async def get_player(self, ctx, *, connect=True):
        if not hasattr(self.bot, "node") or self.bot.node is None:
            raise commands.CommandError("Lavalink node hasn't been initialized.")
        if not ctx.author.voice:
            raise commands.CommandError("You must be connected to a voice channel.")
        if ctx.guild.me.voice and ctx.guild.me.voice.channel != ctx.author.voice.channel:
            raise commands.CommandError("I'm already connected to another voice channel.")
        
        player = self.bot.node.get_player(ctx.guild.id)
        if player is None or not ctx.guild.me.voice:
            if not connect:
                raise commands.CommandError("I'm not connected to a voice channel.")
            else:
                await ctx.author.voice.channel.connect(cls=Player, self_deaf=True)
                player = self.bot.node.get_player(ctx.guild.id)
                player.bound_channel = ctx.channel
                await player.set_volume(65)
                player.voice_channel = ctx.author.voice.channel.id
        return player

    @commands.group(name="queue", invoke_without_command=True)
    async def queue(self, ctx):
        await ctx.send("Use `!queue <subcommand>` to manage the music queue.")

    @queue.command(name="view")
    async def queue_view(self, ctx):
        player = await self.get_player(ctx, connect=False)
        queue_copy = list(player.queue._queue)
        
        if not player.is_playing and not queue_copy:
            embed = discord.Embed(title="Queue", description="The queue is currently empty.", color=0x808080)
            await ctx.send(embed=embed)
            return

        queue_list = []
        
        if player.is_playing and player.track:
            queue_list.append(f"**Now Playing:** [{player.track.title}]({player.track.uri})")
        
        if queue_copy:
            for i, track in enumerate(queue_copy):
                queue_list.append(f"{i + 1}. **[{track.title}]({track.uri})**")

        queue_description = "\n".join(queue_list)
        embed = discord.Embed(title="Current Queue", description=queue_description, color=0x808080)
        await ctx.send(embed=embed)

    @queue.command(name="empty")
    async def queue_empty(self, ctx):
        player = await self.get_player(ctx, connect=False)
        player.queue = asyncio.Queue()
        
        embed = discord.Embed(title="Queue Cleared", description="The music queue has been cleared.", color=0x808080)
        await ctx.send(embed=embed)

    @queue.command(name="shuffle")
    async def queue_shuffle(self, ctx):
        player = await self.get_player(ctx, connect=False)
        queue_items = list(player.queue._queue)
        
        if not queue_items:
            embed = discord.Embed(title="Error", description="The queue is empty.", color=0x808080)
            await ctx.send(embed=embed)
            return
            
        random.shuffle(queue_items)
        
        player.queue = asyncio.Queue()
        for item in queue_items:
            await player.queue.put(item)
            
        embed = discord.Embed(title="Queue Shuffled", description="The music queue has been shuffled.", color=0x808080)
        await ctx.send(embed=embed)

    @queue.command(name="remove")
    async def queue_remove(self, ctx, position: int):
        player = await self.get_player(ctx, connect=False)
        queue_items = list(player.queue._queue)
        
        if position < 1 or position > len(queue_items):
            embed = discord.Embed(title="Error", description="Invalid position.", color=0x808080)
            await ctx.send(embed=embed)
            return

        removed_track = queue_items.pop(position - 1)
        player.queue = asyncio.Queue()
        for track in queue_items:
            await player.queue.put(track)

        embed = discord.Embed(title="Track Removed", description=f"Removed **{removed_track.title}** from the queue.", color=0x808080)
        await ctx.send(embed=embed)

    @queue.command(name="move")
    async def queue_move(self, ctx, position: int, new_position: int):
        player = await self.get_player(ctx, connect=False)
        queue_items = list(player.queue._queue)
        
        if position < 1 or position > len(queue_items) or new_position < 1 or new_position > len(queue_items):
            embed = discord.Embed(title="Error", description="Invalid position.", color=0x808080)
            await ctx.send(embed=embed)
            return

        track = queue_items.pop(position - 1)
        queue_items.insert(new_position - 1, track)
        
        player.queue = asyncio.Queue()
        for track in queue_items:
            await player.queue.put(track)
            
        embed = discord.Embed(title="Track Moved", description=f"Moved **{track.title}** to position {new_position}.", color=0x808080)
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="play")
    async def play(self, ctx, *, query: str):
        player = await self.get_player(ctx)
        result = await player.node.get_tracks(query=query, ctx=ctx)

        if not result:
            embed = discord.Embed(title="Error", description="No results found.", color=0x808080)
            return await ctx.send(embed=embed)

        if isinstance(result, pomice.Playlist):
            tracks = result.tracks
            for track in tracks:
                await player.insert(track)
            embed = discord.Embed(title="Playlist Added", description=f"Added **{len(tracks)}** tracks from the playlist to the queue.", color=0x808080)
            await ctx.send(embed=embed)
        else:
            track = result[0]
            await player.insert(track)
            position = len(list(player.queue._queue))
            embed = discord.Embed(description=f"Added [**{track.title}**]({track.uri}) to the queue.", color=0x808080)
            embed.set_footer(text=f"Position: #{position} in the queue", icon_url=ctx.author.avatar.url)
            await ctx.send(embed=embed)

        if not player.is_playing:
            await self.process_next_track(player, ctx.author)

    @commands.hybrid_command(name="fastforward")
    async def fastforward(self, ctx, position: int):
        player = await self.get_player(ctx, connect=False)
        await player.seek(position * 1000)
        embed = discord.Embed(title="Fast Forwarded", description=f"Fast forwarded to {position} seconds.", color=0x808080)
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="rewind")
    async def rewind(self, ctx, position: int):
        player = await self.get_player(ctx, connect=False)
        await player.seek(-position * 1000)
        embed = discord.Embed(title="Rewinded", description=f"Rewinded to {position} seconds.", color=0x808080)
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="volume")
    async def volume(self, ctx, volume: int):
        if not 0 <= volume <= 100:
            return await ctx.send("Please provide a volume between 0 and 100.")
        player = await self.get_player(ctx, connect=False)
        await player.set_volume(volume)
        embed = discord.Embed(title="Volume Adjusted", description=f"Volume set to {volume}%.", color=0x808080)
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="pause")
    async def pause(self, ctx):
        player = await self.get_player(ctx, connect=False)
        if player.is_playing and not player.is_paused:
            await ctx.message.add_reaction("⏸️")
            await player.set_pause(True)
            embed = discord.Embed(title="Paused", description="The track has been paused.", color=0x808080)
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(title="Error", description="There isn't an active track.", color=0x808080)
            await ctx.send(embed=embed)

    @commands.hybrid_command(name="resume")
    async def resume(self, ctx):
        player = await self.get_player(ctx, connect=False)
        if player.is_playing and player.is_paused:
            await ctx.message.add_reaction("✅")
            await player.set_pause(False)
            embed = discord.Embed(title="Resumed", description="The track has been resumed.", color=0x808080)
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(title="Error", description="There isn't an active track.", color=0x808080)
            await ctx.send(embed=embed)

    @commands.hybrid_command(name="skip")
    async def skip(self, ctx):
        player = await self.get_player(ctx, connect=False)
        if player.is_playing:
            await player.stop()
            embed = discord.Embed(title="Skipped", description="The current track has been skipped.", color=0x808080)
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(title="Error", description="There isn't an active track.", color=0x808080)
            await ctx.send(embed=embed)

    @commands.hybrid_command(name="disconnect")
    async def disconnect(self, ctx):
        player = await self.get_player(ctx, connect=False)
        await player.teardown()
        await ctx.message.add_reaction("👋🏾")
        embed = discord.Embed(title="Disconnected", description="The music player has been disconnected.", color=0x808080)
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="loop")
    async def loop(self, ctx):
        self.looping = not self.looping
        status = "enabled" if self.looping else "disabled"
        embed = discord.Embed(title="Looping", description=f"Looping has been {status}.", color=0x808080)
        await ctx.send(embed=embed)

    async def process_next_track(self, player, user):
        if player.queue.empty():
            return
            
        track = await player.queue.get()
        await player.play(track)
        
        duration_ms = track.info.get('length', 0)
        duration_sec = duration_ms // 1000
        minutes = duration_sec // 60
        seconds = duration_sec % 60
        
        embed = discord.Embed(
            description=f"Started playing **[{track.title}]({track.uri})**",
            color=0x808080
        )
        
        embed.set_footer(
            text=f"Requested by: {user.name} • Duration: {minutes}:{seconds:02d}",
            icon_url=user.avatar.url
        )
        
        await player.bound_channel.send(embed=embed)
        
    @commands.Cog.listener()
    async def on_pomice_track_end(self, player, track, _):
        if self.looping:
            await player.queue.put(track)
        
        ctx = await self.bot.get_context(player.message) if player.message else None
        if ctx:
            await self.process_next_track(player, ctx.author)

async def setup(bot):
    await bot.add_cog(Music(bot))
