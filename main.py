"""
Khabar AI — Newsletter Automation MCP Server
Entrypoint: registers all tools and prompts, then serves over stdio.
"""

import logging

from newsletter.server import mcp
from newsletter.config import validate_config

# Importing these modules registers their @mcp.tool() / @mcp.prompt() handlers.
# The star-imports also keep `main.<tool>` importable for scripts and tests.
from newsletter.research import *       # noqa: F401,F403
from newsletter.editing import *        # noqa: F401,F403
from newsletter.rendering import *      # noqa: F401,F403
from newsletter.distribution import *   # noqa: F401,F403
from newsletter.prompts import *        # noqa: F401,F403

logger = logging.getLogger(__name__)


if __name__ == "__main__":
    logger.info("Starting AI Newsletter MCP Server...")

    if not validate_config():
        logger.error("Configuration validation failed. Please set required environment variables.")
        logger.error("Required: GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REFRESH_TOKEN")
    else:
        logger.info("All required configuration present")

    logger.info("Server ready to accept connections")
    mcp.run()
