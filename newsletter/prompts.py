"""Guided MCP prompts for the newsletter workflow."""

from .server import mcp


@mcp.prompt()
def research_newsletter_prompt() -> str:
    """Prompt to guide through the research phase"""
    return """I need to gather content for this week's AI newsletter. Please help me:

1. Use `fetch_all_research()` to gather content from all sources at once, OR
2. Manually fetch from individual sources:
   - `search_arxiv_papers()` - Latest AI papers (last 7 days)
   - `fetch_github_trending()` - Trending AI repositories
   - `search_product_hunt()` - New AI products
   - `fetch_twitter_trends()` - Viral AI tweets

3. Optional: Check `fetch_past_newsletters()` to understand our format
4. Optional: Use `scan_gmail_feedback()` to see what readers want

Once you have the data, summarize key findings and suggest the "Big Story" for this week."""


@mcp.prompt()
def create_newsletter_prompt() -> str:
    """Prompt to guide through creating the newsletter"""
    return """Based on the research content gathered, create a complete newsletter:

1. Use `create_newsletter_draft()` with the research data
2. Select the most impactful story as the "Big Story"
3. Use `validate_newsletter_content()` to check for issues
4. Use `preview_newsletter()` to see a text preview
5. Use `generate_html_newsletter()` to create the HTML version
6. Use `save_to_drive()` to save to Google Drive

Make the content engaging, concise, and valuable for AI enthusiasts!"""


@mcp.prompt()
def full_automation_prompt() -> str:
    """Complete end-to-end newsletter creation prompt"""
    return """Let's create this week's AI newsletter from scratch:

**PHASE 1: Research**
- Run `fetch_all_research()` to gather all content

**PHASE 2: Create Draft**
- Run `create_newsletter_draft()` with the research data
- Analyze the content and pick the best "Big Story"
- Update the draft with the big story details

**PHASE 3: Quality Check**
- Run `validate_newsletter_content()` to check for issues
- Run `preview_newsletter()` to see the content

**PHASE 4: Generate & Save**
- Run `generate_html_newsletter()` to create HTML
- Run `save_to_drive()` to save to Google Drive

Provide a summary at each phase and ask for approval before moving to the next step."""
