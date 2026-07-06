"""Configuration from environment variables."""

import logging
import os

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class Config:
    """Configuration from environment variables"""
    GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
    GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
    GOOGLE_REFRESH_TOKEN = os.getenv("GOOGLE_REFRESH_TOKEN")
    NEWSLETTER_FOLDER_ID = os.getenv("NEWSLETTER_FOLDER_ID")
    GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
    PRODUCT_HUNT_API_KEY = os.getenv("PRODUCT_HUNT_API_KEY")
    TWITTER_BEARER_TOKEN = os.getenv("TWITTER_BEARER_TOKEN")


def validate_config() -> bool:
    """Validate required environment variables on startup"""
    required = {
        "GOOGLE_CLIENT_ID": Config.GOOGLE_CLIENT_ID,
        "GOOGLE_CLIENT_SECRET": Config.GOOGLE_CLIENT_SECRET,
        "GOOGLE_REFRESH_TOKEN": Config.GOOGLE_REFRESH_TOKEN
    }

    optional = {
        "NEWSLETTER_FOLDER_ID": Config.NEWSLETTER_FOLDER_ID,
        "GITHUB_TOKEN": Config.GITHUB_TOKEN,
        "PRODUCT_HUNT_API_KEY": Config.PRODUCT_HUNT_API_KEY,
        "TWITTER_BEARER_TOKEN": Config.TWITTER_BEARER_TOKEN
    }

    missing_required = [key for key, value in required.items() if not value]
    missing_optional = [key for key, value in optional.items() if not value]

    if missing_required:
        logger.error(f"Missing REQUIRED configuration: {', '.join(missing_required)}")
        logger.error("Google OAuth credentials are required for basic functionality")
        return False

    if missing_optional:
        logger.warning(f"Missing optional configuration: {', '.join(missing_optional)}")
        logger.warning("Some features may be limited")

    logger.info("Configuration validation complete")
    return True
