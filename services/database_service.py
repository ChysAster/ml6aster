"""
Database service module
Handles Firestore database connections and operations
"""
import logging
from typing import Optional

from google.cloud import firestore


class DatabaseService:
    """Service for database operations"""

    def __init__(self):
        self._client: Optional[firestore.Client] = None
        self.logger = logging.getLogger(__name__)

    def get_client(self) -> firestore.Client:
        """Get or create Firestore client (singleton pattern)"""
        if self._client is None:
            try:
                self._client = firestore.Client()
                self.logger.info("Successfully initialized Firestore client")
            except Exception as e:
                self.logger.error(
                    f"Failed to initialize Firestore client: {e}")
                raise

        return self._client

    def health_check(self) -> bool:
        """Check if database connection is healthy"""
        try:
            # Simple operation to test connectivity
            collections = list(self.get_client().collections())
            return True
        except Exception as e:
            self.logger.error(f"Database health check failed: {e}")
            return False
