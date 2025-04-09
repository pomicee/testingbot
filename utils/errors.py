import discord
import traceback
import logging
from discord.ext import commands

from utils.embeds import error_embed

logger = logging.getLogger(__name__)

async def setup_error_handlers(bot):
    """Set up global error handlers for the bot."""
    
    @bot.event
    async def on_command_error(ctx, error):
        """Handle command errors."""
        if hasattr(ctx.command, 'on_error'):
            return  
            
        if isinstance(error, commands.CommandNotFound):
            return  
            
        if isinstance(error, commands.CommandOnCooldown):
            await ctx.send(
                embed=error_embed(
                    f"Slow down! Try again in {error.retry_after:.1f}s."
                )
            )
            return
            
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(
                embed=error_embed(
                    f"Missing required argument: {error.param.name}"
                )
            )
            return
            
        if isinstance(error, commands.BadArgument):
            await ctx.send(
                embed=error_embed(
                    f"Bad argument: {str(error)}"
                )
            )
            return
            
        if isinstance(error, commands.MissingPermissions):
            await ctx.send(
                embed=error_embed(
                    "You don't have the required permissions to use this command."
                )
            )
            return
            
        if isinstance(error, commands.BotMissingPermissions):
            await ctx.send(
                embed=error_embed(
                    f"I need the following permissions: {', '.join(error.missing_permissions)}"
                )
            )
            return
            
        if isinstance(error, commands.CommandError):
            await ctx.send(
                embed=error_embed(
                    str(error)
                )
            )
            return
            
        logger.error(f"Unhandled error in command {ctx.command}: {error}")
        logger.error(traceback.format_exc())
        
        await ctx.send(
            embed=error_embed(
                "An unexpected error occurred. The error has been logged."
            )
        )
        
    @bot.event
    async def on_error(event, *args, **kwargs):
        """Handle generic errors."""
        logger.error(f"Error in event {event}: {traceback.format_exc()}")
