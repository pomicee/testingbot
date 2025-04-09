import os
import time
import asyncio
import discord
from discord.ext import commands
import jishaku

from config import Config
from utils.logging import setup_logger
from utils.errors import setup_error_handlers

logger = setup_logger(__name__)

class MusicBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        super().__init__(
            command_prefix=Config.PREFIX,
            intents=intents,
            case_insensitive=True,
            help_command=None 
        )
        
        self.start_time = time.time()
        jishaku.Flags.OWNER_IDS = Config.OWNER_IDS
        self.lavalink_node = None
        self.config = Config
        
    async def start(self):
        """Start the bot."""
        await self._load_extensions()
        await setup_error_handlers(self)
        await super().start(self.config.TOKEN)
    
    async def _load_extensions(self):
        """Load all extensions."""
        await self.load_extension('jishaku')
        logger.info("Loaded jishaku extension")
        
        for filename in os.listdir('./cogs'):
            if filename.endswith('.py') and not filename.startswith('_'):
                cog_name = f'cogs.{filename[:-3]}'
                try:
                    await self.load_extension(cog_name)
                    logger.info(f"Loaded extension: {cog_name}")
                except Exception as e:
                    logger.error(f"Failed to load extension {cog_name}: {e}")
    
    async def setup_hook(self):
        """Setup hook that runs before the bot starts processing events."""
        await self.tree.sync()
        logger.info("Slash commands have been synced")
    
    async def on_ready(self):
        """Event that triggers when the bot is ready."""
        logger.info(f"Logged in as {self.user.name} ({self.user.id})")
        logger.info(f"Discord.py version: {discord.__version__}")
        
        activity = discord.Game(name=self.config.STATUS_MESSAGE)
        await self.change_presence(activity=activity)
