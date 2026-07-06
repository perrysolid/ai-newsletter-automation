"""FastMCP server instance shared by all tool modules."""

import logging

from fastmcp import FastMCP

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

mcp = FastMCP("AI Newsletter Automation")
