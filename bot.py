import discord
from discord.ext import commands
import os
import jishaku
from config import Config
import time
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)
bot.start_time = time.time()
jishaku.OWNER_ID = 1252001166703853588  

async def load_cogs():
    """Load all cogs from the cogs folder."""
    for filename in os.listdir('./cogs'):
        if filename.endswith('.py') and filename != '__init__.py':
            cog_name = f'cogs.{filename[:-3]}'
            try:
                await bot.load_extension(cog_name)
                print(f'Loaded {cog_name}')
            except commands.ExtensionAlreadyLoaded:
                print(f'{cog_name} is already loaded.')
            except Exception as e:
                print(f'Failed to load {cog_name}: {e}')

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name} - {bot.user.id}")
    
    activity = discord.Game(name="Playing Music on iOS") 
    await bot.change_presence(activity=activity)  

@bot.event
async def setup_hook():
    """Sync the app commands with Discord and load Jishaku."""
    await bot.load_extension('jishaku')  
    await load_cogs()  
    await bot.tree.sync()  
    print("Slash commands have been synced.")

@bot.command(name='jske', hidden=True)
async def jishaku_command(ctx, *, code: str):
    """Evaluate a code snippet."""
    try:
        result = eval(code)
        embed = discord.Embed(title="Jishaku Result", description=f"```python\n{result}```", color=0x808080)  
        await ctx.send(embed=embed)
    except Exception as e:
        embed = discord.Embed(title="Error", description=f"```python\n{str(e)}```", color=0xff0000)  
        await ctx.send(embed=embed)

if __name__ == "__main__":
    bot.run(Config.TOKEN)
