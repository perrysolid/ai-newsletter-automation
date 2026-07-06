"""Editing phase tools: draft creation, organization, validation, preview."""

import logging
from datetime import datetime
from typing import Dict, List, Optional

from .server import mcp

logger = logging.getLogger(__name__)


@mcp.tool()
def create_newsletter_draft(research_content: Dict, issue_number: int = 1) -> Dict:
    """
    Create a structured newsletter draft from research content.

    Args:
        research_content: Dictionary containing all gathered research data
        issue_number: Newsletter issue number (default: 1)

    Returns:
        Structured newsletter draft with all sections organized
    """
    try:
        draft = {
            "metadata": {
                "issue_number": issue_number,
                "date": datetime.now().strftime("%B %d, %Y"),
                "title": "Khabar AI"
            },
            "sections": {
                "big_story": {
                    "title": "",
                    "content": "",
                    "source": ""
                },
                "quick_updates": [],
                "top_papers": research_content.get("papers", [])[:5],
                "github_repos": research_content.get("repositories", [])[:5],
                "tutorials": research_content.get("tutorials", []),
                "ai_products": research_content.get("products", [])[:3],
                "tweets": research_content.get("tweets", [])[:3],
                "closing_notes": ""
            },
            "status": "draft",
            "created_at": datetime.now().isoformat()
        }

        logger.info(f"Created newsletter draft #{issue_number}")

        return {
            "status": "success",
            "draft": draft
        }

    except Exception as e:
        logger.error(f"Failed to create draft: {str(e)}")
        return {
            "status": "error",
            "message": str(e)
        }


@mcp.tool()
def organize_content_sections(
    raw_content: Dict,
    priorities: Optional[List[str]] = None
) -> Dict:
    """
    Organize research content into newsletter sections with priorities.

    Args:
        raw_content: Raw research data to organize
        priorities: List of section names in priority order

    Returns:
        Content organized by sections with prioritization applied
    """
    if priorities is None:
        priorities = ["big_story", "papers", "products", "repositories", "tweets"]

    organized = {
        "sections": {},
        "metadata": {
            "total_items": 0,
            "sections_count": 0
        }
    }

    for priority in priorities:
        if priority in raw_content:
            organized["sections"][priority] = raw_content[priority]
            organized["metadata"]["sections_count"] += 1
            if isinstance(raw_content[priority], list):
                organized["metadata"]["total_items"] += len(raw_content[priority])

    logger.info(f"Organized content into {organized['metadata']['sections_count']} sections")

    return {
        "status": "success",
        "organized_content": organized
    }


@mcp.tool()
def validate_newsletter_content(draft_content: Dict) -> Dict:
    """
    Validate newsletter content for completeness and quality.

    Args:
        draft_content: Newsletter draft to validate

    Returns:
        Validation results with warnings and errors
    """
    issues = []
    warnings = []

    sections = draft_content.get("sections", {})

    # Check for minimum content
    if len(sections.get("top_papers", [])) < 3:
        warnings.append("Less than 3 papers - consider adding more")

    if len(sections.get("github_repos", [])) < 3:
        warnings.append("Less than 3 GitHub repos - consider adding more")

    # Check for big story
    if not sections.get("big_story", {}).get("content"):
        issues.append("Big story content is missing")

    if not sections.get("big_story", {}).get("title"):
        issues.append("Big story title is missing")

    # Check metadata
    metadata = draft_content.get("metadata", {})
    if not metadata.get("issue_number"):
        issues.append("Issue number is missing")

    logger.info(f"Validation complete: {len(issues)} issues, {len(warnings)} warnings")

    return {
        "status": "success" if not issues else "warning",
        "valid": len(issues) == 0,
        "issues": issues,
        "warnings": warnings,
        "sections_count": len(sections)
    }


@mcp.tool()
def preview_newsletter(draft_content: Dict) -> Dict:
    """
    Generate a text preview of the newsletter for quick review.

    Args:
        draft_content: Newsletter draft content

    Returns:
        Plain text preview with content summary
    """
    sections = draft_content.get("sections", {})
    metadata = draft_content.get("metadata", {})

    preview = f"""
{'='*60}
{metadata.get('title', 'Newsletter Preview')}
Issue #{metadata.get('issue_number', 'N/A')} | {metadata.get('date', '')}
{'='*60}

📊 CONTENT SUMMARY:
- Papers: {len(sections.get('top_papers', []))}
- GitHub Repos: {len(sections.get('github_repos', []))}
- Products: {len(sections.get('ai_products', []))}
- Tweets: {len(sections.get('tweets', []))}

🎯 BIG STORY:
{sections.get('big_story', {}).get('title', 'Not set')}

📄 TOP PAPERS:
"""

    for i, paper in enumerate(sections.get("top_papers", [])[:3], 1):
        preview += f"\n{i}. {paper.get('title', 'Untitled')}\n"

    preview += f"\n{'='*60}\n"

    return {
        "status": "success",
        "preview": preview,
        "word_count": len(preview.split())
    }
