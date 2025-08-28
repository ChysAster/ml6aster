import os
from typing import Optional


class Config:
    """Application configuration"""

    # Server configuration
    PORT: int = int(os.getenv('PORT', '8080'))
    DEBUG: bool = os.getenv('DEBUG', 'false').lower() == 'true'
    LOG_LEVEL: str = os.getenv('LOG_LEVEL', 'INFO')

    # Google Cloud configuration
    GOOGLE_CLOUD_PROJECT: Optional[str] = os.getenv('GOOGLE_CLOUD_PROJECT')
    SECRET_NAME: str = 'basic-auth'
    ELASTICSEARCH_SECRET_NAME: str = 'elasticsearch-credentials'

    # Elasticsearch configuration
    ELASTICSEARCH_URL: str = os.getenv(
        'ELASTICSEARCH_URL', 'http://localhost:9200')
    ELASTICSEARCH_USERNAME: Optional[str] = os.getenv('ELASTICSEARCH_USERNAME')
    ELASTICSEARCH_PASSWORD: Optional[str] = os.getenv('ELASTICSEARCH_PASSWORD')
    ELASTICSEARCH_API_KEY: Optional[str] = os.getenv('ELASTICSEARCH_API_KEY')
    ELASTICSEARCH_API_KEY_ID: Optional[str] = os.getenv(
        'ELASTICSEARCH_API_KEY_ID')

    # Database configuration
    RECIPES_COLLECTION: str = 'recipes'
    RECIPES_INDEX: str = 'recipes'

    # Pagination limits
    DEFAULT_LIMIT: int = 50
    MAX_LIMIT: int = 200
    MIN_LIMIT: int = 1

    # Fallback credentials for development
    FALLBACK_CREDENTIALS: dict = {"test": "test"}

    @classmethod
    def validate_limit(cls, limit: int) -> int:
        """Validate and normalize pagination limit"""
        return max(cls.MIN_LIMIT, min(cls.MAX_LIMIT, int(limit)))

    @classmethod
    def get_elasticsearch_auth_from_env(cls) -> tuple:
        """Get Elasticsearch authentication from environment variables"""
        if cls.ELASTICSEARCH_API_KEY_ID and cls.ELASTICSEARCH_API_KEY:
            return "api_key", (cls.ELASTICSEARCH_API_KEY_ID, cls.ELASTICSEARCH_API_KEY)
        elif cls.ELASTICSEARCH_API_KEY:
            return "api_key_single", cls.ELASTICSEARCH_API_KEY
        elif cls.ELASTICSEARCH_USERNAME and cls.ELASTICSEARCH_PASSWORD:
            return "basic_auth", (cls.ELASTICSEARCH_USERNAME, cls.ELASTICSEARCH_PASSWORD)
        else:
            return None, None
