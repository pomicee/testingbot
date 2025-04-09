import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    TOKEN = os.getenv("DISCORD_TOKEN")
    PREFIX = os.getenv("PREFIX", "!")
    OWNER_IDS = [int(id) for id in os.getenv("OWNER_IDS", "1252001166703853588").split(",")]
    LAVALINK = {
        "host": os.getenv("LAVALINK_HOST", "localhost"),
        "port": int(os.getenv("LAVALINK_PORT", 2333)),
        "password": os.getenv("LAVALINK_PASSWORD", "youshallnotpass"),
        "identifier": os.getenv("LAVALINK_IDENTIFIER", "MAIN"),
        "secure": os.getenv("LAVALINK_SECURE", "false").lower() == "true"
    }
    
    DEFAULT_VOLUME = int(os.getenv("DEFAULT_VOLUME", 65))
    
    STATUS_MESSAGE = os.getenv("STATUS_MESSAGE", "Playing Music on iOS")
