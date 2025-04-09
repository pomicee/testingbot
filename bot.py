import asyncio
from core.bot import MusicBot

if __name__ == "__main__":
    bot = MusicBot()
    asyncio.run(bot.start())
