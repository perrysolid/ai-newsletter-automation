"""Google API service factory with OAuth token refresh."""

import logging

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from .config import Config

logger = logging.getLogger(__name__)


def get_google_service(service_name: str, version: str):
    """Create Google API service with credentials and automatic token refresh"""
    try:
        if not all([Config.GOOGLE_CLIENT_ID, Config.GOOGLE_CLIENT_SECRET, Config.GOOGLE_REFRESH_TOKEN]):
            raise ValueError("Missing required Google OAuth credentials")

        creds = Credentials(
            token=None,
            refresh_token=Config.GOOGLE_REFRESH_TOKEN,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=Config.GOOGLE_CLIENT_ID,
            client_secret=Config.GOOGLE_CLIENT_SECRET
        )

        # Refresh token if needed
        if not creds.valid:
            if creds.expired and creds.refresh_token:
                creds.refresh(Request())

        return build(service_name, version, credentials=creds)

    except Exception as e:
        logger.error(f"Failed to create Google service: {str(e)}")
        raise
