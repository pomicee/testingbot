import asyncio
import logging
import requests
import pomice

logger = logging.getLogger(__name__)

class MusicPlayer(pomice.Player):
    """
    Custom player class with additional functionality.
    """
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
        """Play a track and update the current track reference."""
        self.track = track
        await super().play(track)

    async def insert(self, track, filter=True):
        """
        Insert a track into the queue.
        
        Args:
            track: The track to insert
            filter: Whether to filter track metadata (YouTube)
        
        Returns:
            The track that was inserted
        """
        if filter and track.info.get("sourceName", "YouTube") == "youtube":
            try:
                response = requests.get(
                    "https://metadata-filter.vercel.app/api/youtube", 
                    params=dict(track=track.title),
                    timeout=5
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get("status") == "success":
                        track.title = data["data"].get("track")
            except Exception as e:
                logger.error(f"Error filtering track metadata: {e}")
                
        await self.queue.put(track)
        return track
    
    async def skip(self):
        """Skip the current track."""
        await self.stop()
    
    async def clear_queue(self):
        """Clear the queue."""
        self.queue = asyncio.Queue()
    
    @property
    def queue_length(self):
        """Get the number of tracks in the queue."""
        return len(self.queue._queue)
    
    @property
    def queue_list(self):
        """Get a list of tracks in the queue."""
        return list(self.queue._queue)
    
    def get_queue_position(self, track):
        """Get position of a track in the queue."""
        return self.queue_list.index(track) if track in self.queue_list else -1
