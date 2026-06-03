from prisma import Prisma
import asyncio
from src.utils.config import settings
import logging

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

class DatabaseService:
    def __init__(self):
        # Create client instance but do NOT connect automatically
        self.prisma = Prisma(datasource={'url': settings.DATABASE_URL})
        self._connected = False

    async def connect(self, max_retries: int = 5, base_delay: float = 1.0):
        if self._connected:
            logger.info("Already connected to database")
            return
        for attempt in range(max_retries):
            try:
                await self.prisma.connect()
                self._connected = True
                logger.info("Connected to database")
                return
            except Exception as e:
                if attempt == max_retries - 1:
                    logger.error(f"Failed to connect to database after {max_retries} attempts: {e}")
                    raise
                # Exponential backoff
                delay = base_delay * (2 ** attempt)
                logger.warning(f"Database connection failed (attempt {attempt + 1}/{max_retries}), retrying in {delay:.2f} seconds...")
                await asyncio.sleep(delay)

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
