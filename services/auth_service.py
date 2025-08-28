"""
Authentication service module
Handles user authentication and password management
"""
import json
import logging
from typing import Dict, Optional

from google.cloud import secretmanager

from config import Config


class AuthService:
    """Service for handling authentication"""

    def __init__(self):
        self._passwords: Optional[Dict[str, str]] = None
        self.logger = logging.getLogger(__name__)

    def get_passwords(self) -> Dict[str, str]:
        """Retrieve passwords from Google Cloud Secret Manager with fallback"""
        if self._passwords is not None:
            return self._passwords

        try:
            return self._load_passwords_from_secret_manager()
        except Exception as e:
            self.logger.error(
                f"Failed to load passwords from Secret Manager: {e}")
            return self._use_fallback_passwords()

    def _load_passwords_from_secret_manager(self) -> Dict[str, str]:
        """Load passwords from Google Cloud Secret Manager"""
        if not Config.GOOGLE_CLOUD_PROJECT:
            self.logger.warning("GOOGLE_CLOUD_PROJECT not set, using fallback")
            return self._use_fallback_passwords()

        client = secretmanager.SecretManagerServiceClient()
        secret_name = f"projects/{Config.GOOGLE_CLOUD_PROJECT}/secrets/{Config.SECRET_NAME}/versions/latest"

        response = client.access_secret_version(request={"name": secret_name})
        secret_value = response.payload.data.decode("UTF-8")

        self._passwords = json.loads(secret_value)
        self.logger.info("Successfully loaded passwords from Secret Manager")
        return self._passwords

    def _use_fallback_passwords(self) -> Dict[str, str]:
        """Use fallback passwords for development"""
        self._passwords = Config.FALLBACK_CREDENTIALS
        self.logger.warning("Using fallback credentials")
        return self._passwords

    def authenticate(self, username: str, password: str) -> Optional[Dict[str, str]]:
        """Authenticate a user with username and password"""
        passwords = self.get_passwords()

        if passwords.get(username) == password:
            return {"sub": username}

        return None
