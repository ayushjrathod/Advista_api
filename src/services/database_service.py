from prisma import Prisma
from src.utils.config import settings
import logging

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# TODO: implement retries maybe exponential backoff
class DatabaseService:
    def __init__(self):
        # Create client instance but do NOT connect automatically
        self.prisma = Prisma(datasource={'url': settings.DATABASE_URL})
        self._connected = False

    async def connect(self):
        if not self._connected:
            try:
                await self.prisma.connect()
                self._connected = True
                logger.info("Connected to database")
            except Exception as e:
                logger.error(f"Error connecting to database: {e}")
                raise

    async def disconnect(self):
        if self._connected:
            try:
                await self.prisma.disconnect()
                self._connected = False
                logger.info("Disconnected from database")
            except Exception as e:
                logger.error(f"Error disconnecting from database: {e}")
                raise

    def is_connected(self) -> bool:
        """Return whether the Prisma client is connected."""
        try:
            if hasattr(self.prisma, "is_connected"):
                return self.prisma.is_connected()
        except Exception:
            pass
        return self._connected

# Exporting singleton instance
db = DatabaseService()
