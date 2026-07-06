"""
AI Newsletter MCP Server - Fixed & Enhanced Version
Built with FastMCP for easy tool creation and management
"""

from fastmcp import FastMCP
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import os
from dotenv import load_dotenv
import logging
from functools import wraps
import time

# External API imports
import arxiv
import requests
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
import io
import base64
from email.mime.text import MIMEText

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Initialize FastMCP server
mcp = FastMCP("AI Newsletter Automation")

# ==================== CONFIGURATION ====================

class Config:
    """Configuration from environment variables"""
    GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
    GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
    GOOGLE_REFRESH_TOKEN = os.getenv("GOOGLE_REFRESH_TOKEN")
    NEWSLETTER_FOLDER_ID = os.getenv("NEWSLETTER_FOLDER_ID")
    GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
    PRODUCT_HUNT_API_KEY = os.getenv("PRODUCT_HUNT_API_KEY")
    TWITTER_BEARER_TOKEN = os.getenv("TWITTER_BEARER_TOKEN")


# ==================== HELPER FUNCTIONS ====================

def rate_limit(calls_per_minute: int = 10):
    """Decorator to rate limit function calls"""
    def decorator(func):
        last_called = [0.0]
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            elapsed = time.time() - last_called[0]
            wait_time = 60.0 / calls_per_minute - elapsed
            if wait_time > 0:
                time.sleep(wait_time)
            last_called[0] = time.time()
            return func(*args, **kwargs)
        return wrapper
    return decorator


def safe_api_call(func):
    """Decorator for safe API calls with error handling"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except requests.Timeout:
            logger.error(f"{func.__name__}: Request timeout")
            return {"status": "error", "message": "Request timeout"}
        except requests.RequestException as e:
            logger.error(f"{func.__name__}: Request failed - {str(e)}")
            return {"status": "error", "message": f"Request failed: {str(e)}"}
        except Exception as e:
            logger.error(f"{func.__name__}: Unexpected error - {str(e)}")
            return {"status": "error", "message": f"Unexpected error: {str(e)}"}
    return wrapper


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


# ==================== RESEARCH PHASE TOOLS ====================

@mcp.tool()
@safe_api_call
def fetch_past_newsletters(folder_id: Optional[str] = None, count: int = 5) -> Dict:
    """
    Retrieve past newsletters from Google Drive to understand format and performance.
    
    Args:
        folder_id: Google Drive folder ID (uses env var if not provided)
        count: Number of past newsletters to fetch (default: 5)
    
    Returns:
        Dictionary containing newsletter metadata and performance metrics
    """
    if folder_id is None:
        folder_id = Config.NEWSLETTER_FOLDER_ID
    
    if not folder_id:
        return {
            "status": "error",
            "message": "No folder ID provided. Set NEWSLETTER_FOLDER_ID environment variable."
        }
    
    service = get_google_service('drive', 'v3')
    
    # Query files in the folder
    query = f"'{folder_id}' in parents and mimeType='text/html'"
    results = service.files().list(
        q=query,
        pageSize=count,
        orderBy='createdTime desc',
        fields="files(id, name, createdTime, description)"
    ).execute()
    
    files = results.get('files', [])
    
    newsletters = []
    for file in files:
        newsletters.append({
            "id": file['id'],
            "title": file['name'],
            "date": file['createdTime'],
            "drive_link": f"https://drive.google.com/file/d/{file['id']}/view"
        })
    
    logger.info(f"Fetched {len(newsletters)} past newsletters")
    
    return {
        "status": "success",
        "count": len(newsletters),
        "newsletters": newsletters
    }


@mcp.tool()
@safe_api_call
def scan_gmail_feedback(days_back: int = 7, keywords: Optional[List[str]] = None) -> Dict:
    """
    Scan Gmail for reader feedback and engagement metrics.
    
    Args:
        days_back: Number of days to look back (default: 7)
        keywords: Keywords to filter feedback emails (optional)
    
    Returns:
        Summary of feedback with themes and common requests
    """
    service = get_google_service('gmail', 'v1')
    
    # Build search query
    date_threshold = (datetime.now() - timedelta(days=days_back)).strftime('%Y/%m/%d')
    query = f"after:{date_threshold} subject:(newsletter OR feedback OR reply)"
    
    if keywords:
        keyword_query = " OR ".join(keywords)
        query += f" ({keyword_query})"
    
    # Search messages
    results = service.users().messages().list(
        userId='me',
        q=query,
        maxResults=50
    ).execute()
    
    messages = results.get('messages', [])
    
    feedback_data = {
        "total_responses": len(messages),
        "emails": []
    }
    
    # Fetch message details
    for msg in messages[:10]:  # Limit to first 10 for processing
        message = service.users().messages().get(
            userId='me',
            id=msg['id'],
            format='full'
        ).execute()
        
        # Extract subject and snippet
        headers = message['payload']['headers']
        subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'No Subject')
        
        feedback_data["emails"].append({
            "subject": subject,
            "snippet": message.get('snippet', ''),
            "date": message.get('internalDate', '')
        })
    
    logger.info(f"Scanned {len(messages)} feedback emails")
    
    return {
        "status": "success",
        "feedback_summary": feedback_data
    }


@mcp.tool()
@safe_api_call
@rate_limit(calls_per_minute=30)
def search_arxiv_papers(
    query: str = "artificial intelligence",
    max_results: int = 10,
    days_back: int = 7
) -> Dict:
    """
    Search arXiv for latest AI research papers.
    
    Args:
        query: Search query for papers (default: "artificial intelligence")
        max_results: Maximum number of results (default: 10)
        days_back: Papers published in last N days (default: 7)
    
    Returns:
        List of papers with titles, authors, summaries, and links
    """
    date_threshold = datetime.now() - timedelta(days=days_back)
    
    # Search arXiv
    search = arxiv.Search(
        query=query,
        max_results=max_results * 2,  # Fetch more to filter by date
        sort_by=arxiv.SortCriterion.SubmittedDate
    )
    
    papers = []
    client = arxiv.Client()
    for result in client.results(search):
        # Filter by date
        if result.published.replace(tzinfo=None) >= date_threshold:
            papers.append({
                "title": result.title,
                "authors": [author.name for author in result.authors[:3]],  # First 3 authors
                "summary": result.summary[:400] + "..." if len(result.summary) > 400 else result.summary,
                "published": result.published.strftime("%Y-%m-%d"),
                "url": result.entry_id,
                "pdf_url": result.pdf_url,
                "categories": result.categories[:3]
            })
            
            if len(papers) >= max_results:
                break
    
    logger.info(f"Found {len(papers)} relevant papers on arXiv")
    
    return {
        "status": "success",
        "count": len(papers),
        "papers": papers,
        "query": query
    }


@mcp.tool()
@safe_api_call
@rate_limit(calls_per_minute=30)
def fetch_github_trending(
    language: str = "python",
    timeframe: str = "weekly",
    topic: str = "artificial-intelligence"
) -> Dict:
    """
    Fetch trending AI repositories from GitHub.
    
    Args:
        language: Programming language filter (default: "python")
        timeframe: Time period - daily, weekly, monthly (default: "weekly")
        topic: GitHub topic to filter (default: "artificial-intelligence")
    
    Returns:
        List of trending repositories with stats
    """
    # Calculate date for trending
    if timeframe == "daily":
        date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    elif timeframe == "weekly":
        date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    else:
        date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    
    # GitHub API endpoint
    url = "https://api.github.com/search/repositories"
    
    headers = {"Accept": "application/vnd.github.v3+json"}
    if Config.GITHUB_TOKEN:
        headers["Authorization"] = f"token {Config.GITHUB_TOKEN}"
    
    params = {
        "q": f"language:{language} created:>{date} topic:{topic}",
        "sort": "stars",
        "order": "desc",
        "per_page": 10
    }
    
    response = requests.get(url, params=params, headers=headers, timeout=15)
    response.raise_for_status()
    data = response.json()
    
    repos = []
    for item in data.get("items", []):
        repos.append({
            "name": item["name"],
            "full_name": item["full_name"],
            "description": item.get("description", "No description available"),
            "stars": item["stargazers_count"],
            "forks": item["forks_count"],
            "url": item["html_url"],
            "language": item.get("language", "N/A"),
            "topics": item.get("topics", [])[:5],
            "created_at": item["created_at"]
        })
    
    logger.info(f"Found {len(repos)} trending GitHub repositories")
    
    return {
        "status": "success",
        "count": len(repos),
        "repositories": repos,
        "timeframe": timeframe
    }


@mcp.tool()
@safe_api_call
@rate_limit(calls_per_minute=20)
def search_product_hunt(days_back: int = 7, limit: int = 10) -> Dict:
    """
    Search Product Hunt for new AI tools and products.
    
    Args:
        days_back: Products launched in last N days (default: 7)
        limit: Maximum number of products (default: 10)
    
    Returns:
        List of AI products with votes and details
    """
    if not Config.PRODUCT_HUNT_API_KEY:
        return {
            "status": "error",
            "message": "Product Hunt API key not configured. Set PRODUCT_HUNT_API_KEY environment variable."
        }
    
    # Product Hunt GraphQL API
    url = "https://api.producthunt.com/v2/api/graphql"
    
    headers = {
        "Authorization": f"Bearer {Config.PRODUCT_HUNT_API_KEY}",
        "Content-Type": "application/json"
    }
    
    query = """
    query {
      posts(order: VOTES, topic: "artificial-intelligence", first: %d) {
        edges {
          node {
            name
            tagline
            description
            votesCount
            url
            createdAt
            topics {
              edges {
                node {
                  name
                }
              }
            }
          }
        }
      }
    }
    """ % limit
    
    response = requests.post(url, json={"query": query}, headers=headers, timeout=15)
    response.raise_for_status()
    data = response.json()
    
    products = []
    for edge in data.get("data", {}).get("posts", {}).get("edges", []):
        node = edge["node"]
        products.append({
            "name": node["name"],
            "tagline": node["tagline"],
            "description": (node.get("description", "") or "")[:200],
            "votes": node["votesCount"],
            "url": node["url"],
            "launch_date": node["createdAt"]
        })
    
    logger.info(f"Found {len(products)} AI products on Product Hunt")
    
    return {
        "status": "success",
        "count": len(products),
        "products": products
    }


@mcp.tool()
@safe_api_call
@rate_limit(calls_per_minute=15)
def fetch_twitter_trends(
    hashtags: Optional[List[str]] = None,
    min_likes: int = 100,
    days_back: int = 7
) -> Dict:
    """
    Fetch viral AI-related tweets and trends.
    
    Args:
        hashtags: List of hashtags to track (default: ["AI", "MachineLearning", "LLM"])
        min_likes: Minimum likes threshold (default: 100)
        days_back: Tweets from last N days (default: 7)
    
    Returns:
        List of trending tweets with engagement metrics
    """
    if not Config.TWITTER_BEARER_TOKEN:
        return {
            "status": "error",
            "message": "Twitter API token not configured. Set TWITTER_BEARER_TOKEN environment variable."
        }
    
    if hashtags is None:
        hashtags = ["AI", "MachineLearning", "LLM", "ChatGPT", "GenerativeAI"]
    
    # Twitter API v2 endpoint
    url = "https://api.twitter.com/2/tweets/search/recent"
    
    headers = {
        "Authorization": f"Bearer {Config.TWITTER_BEARER_TOKEN}"
    }
    
    # Build query
    hashtag_query = " OR ".join([f"#{tag}" for tag in hashtags])
    query = f"({hashtag_query}) -is:retweet lang:en"
    
    params = {
        "query": query,
        "max_results": 100,
        "tweet.fields": "public_metrics,created_at,author_id",
        "expansions": "author_id",
        "user.fields": "username,name"
    }
    
    response = requests.get(url, params=params, headers=headers, timeout=15)
    response.raise_for_status()
    data = response.json()
    
    tweets = []
    users = {user["id"]: user for user in data.get("includes", {}).get("users", [])}
    
    for tweet in data.get("data", []):
        metrics = tweet.get("public_metrics", {})
        if metrics.get("like_count", 0) >= min_likes:
            author = users.get(tweet["author_id"], {})
            tweets.append({
                "text": tweet["text"][:280],
                "author": f"@{author.get('username', 'unknown')}",
                "author_name": author.get('name', 'Unknown'),
                "likes": metrics.get("like_count", 0),
                "retweets": metrics.get("retweet_count", 0),
                "replies": metrics.get("reply_count", 0),
                "created_at": tweet["created_at"],
                "url": f"https://twitter.com/{author.get('username', 'i')}/status/{tweet['id']}"
            })
    
    # Sort by engagement
    tweets.sort(key=lambda x: x["likes"] + x["retweets"] * 2, reverse=True)
    
    logger.info(f"Found {len(tweets)} trending AI tweets")
    
    return {
        "status": "success",
        "count": len(tweets),
        "trending_tweets": tweets[:10]
    }


# ==================== EDITING PHASE TOOLS ====================

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


# ==================== DESIGNING PHASE TOOLS ====================

@mcp.tool()
def generate_html_newsletter(draft_content: Dict, template: str = "default") -> Dict:
    """
    Convert newsletter draft into HTML with design specifications.

    Args:
        draft_content: Newsletter draft content dictionary
        template: Template style to use (default, modern, minimal)

    Returns:
        Complete HTML newsletter ready for distribution
    """
    from html import escape
    from collections import Counter

    try:
        metadata = draft_content.get("metadata", {})
        sections = draft_content.get("sections", {})

        # Design tokens — editorial print aesthetic, email-safe
        INK = "#191512"          # near-black ink
        PAPER = "#FBF7ED"        # warm paper
        PAGE = "#EFE8D8"         # page background
        ACCENT = "#C43D12"       # vermilion
        MUTED = "#867B66"        # faded ink
        BODY_TXT = "#453E31"     # body copy
        RULE = "#D8CDB4"         # hairline rule
        SERIF = "Georgia, 'Times New Roman', serif"
        MONO = "'Courier New', Courier, monospace"

        issue_date = escape(str(metadata.get('date', datetime.now().strftime("%B %d, %Y"))))

        def eyebrow(text, color=ACCENT):
            return (f'<div style="font-family:{MONO};font-size:11px;font-weight:bold;'
                    f'letter-spacing:3px;color:{color};padding-bottom:10px;">{text}</div>')

        def section_band(label, count_label=""):
            right = (f'<td align="right" style="font-family:{MONO};font-size:10px;'
                     f'letter-spacing:2px;color:{PAPER};opacity:0.7;padding:11px 40px 11px 0;">{count_label}</td>') if count_label else ''
            return (f'<tr><td style="background-color:{INK};">'
                    f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>'
                    f'<td style="font-family:{MONO};font-size:11px;font-weight:bold;letter-spacing:3px;'
                    f'color:{PAPER};padding:11px 0 11px 40px;">{label}</td>{right}'
                    f'</tr></table></td></tr>')

        def dotted_rule(pad="0 40px"):
            return (f'<tr><td style="padding:{pad};">'
                    f'<div style="border-top:1px dashed {RULE};font-size:0;line-height:0;">&nbsp;</div></td></tr>')

        def mono_link(href, label):
            return (f'<a href="{escape(href, quote=True)}" target="_blank" style="font-family:{MONO};'
                    f'font-size:12px;font-weight:bold;letter-spacing:1px;color:{ACCENT};'
                    f'text-decoration:none;border-bottom:2px solid {ACCENT};padding-bottom:1px;">{label}</a>')

        def tag_chip(text):
            return (f'<span style="font-family:{MONO};font-size:10px;letter-spacing:1px;color:{INK};'
                    f'border:1px solid {INK};padding:2px 7px;margin-right:6px;white-space:nowrap;">{escape(text)}</span>')

        def compact_num(n):
            n = int(n or 0)
            if n >= 1_000_000:
                return f"{n/1_000_000:.1f}M"
            if n >= 1_000:
                return f"{n/1_000:.1f}K"
            return str(n)

        def bar_row(label, value, max_value, display, color=INK):
            pct = int(round((value / max_value) * 100)) if max_value else 0
            pct = min(max(pct, 4), 100)
            rest = 100 - pct
            return (f'<tr>'
                    f'<td width="150" valign="middle" style="font-family:{MONO};font-size:10px;letter-spacing:1px;'
                    f'color:{INK};padding:5px 10px 5px 0;white-space:nowrap;">{escape(label)}</td>'
                    f'<td valign="middle" style="padding:5px 0;">'
                    f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>'
                    f'<td width="{pct}%" style="background-color:{color};font-size:8px;line-height:13px;">&nbsp;</td>'
                    f'<td width="{rest}%" style="background-color:{PAGE};font-size:8px;line-height:13px;">&nbsp;</td>'
                    f'</tr></table></td>'
                    f'<td width="64" align="right" valign="middle" style="font-family:{MONO};font-size:10px;'
                    f'color:{MUTED};padding:5px 0 5px 10px;white-space:nowrap;">{display}</td></tr>')

        def figure_box(caption, rows_html):
            return (f'<tr><td style="padding:24px 40px 4px;">'
                    f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border:1px solid {INK};">'
                    f'<tr><td style="border-bottom:1px solid {INK};background-color:{PAGE};font-family:{MONO};'
                    f'font-size:10px;font-weight:bold;letter-spacing:2px;color:{INK};padding:8px 14px;">{caption}</td></tr>'
                    f'<tr><td style="padding:12px 14px;">'
                    f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0">{rows_html}</table>'
                    f'</td></tr></table></td></tr>')

        papers = sections.get("top_papers", [])
        repos = sections.get("github_repos", [])
        products = sections.get("ai_products", [])
        tweets = sections.get("tweets", [])

        # Preview text shown next to the subject line in inboxes
        big_story = sections.get("big_story", {})
        preview_bits = []
        if big_story.get("title"):
            preview_bits.append(big_story["title"])
        if papers:
            preview_bits.append(f"{len(papers)} new papers")
        if repos:
            preview_bits.append(f"{len(repos)} trending repos")
        preheader = escape(" · ".join(preview_bits) or "This week in AI")

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="color-scheme" content="light">
    <meta name="supported-color-schemes" content="light">
    <title>Khabar AI</title>
</head>
<body style="margin:0;padding:0;background-color:{PAGE};">
    <div style="display:none;max-height:0;overflow:hidden;mso-hide:all;">{preheader}&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;</div>
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:{PAGE};">
    <tr><td align="center" style="padding:32px 12px;">
    <table role="presentation" width="640" cellpadding="0" cellspacing="0" style="width:640px;max-width:100%;background-color:{PAPER};border:1px solid {INK};">

        <!-- Masthead -->
        <tr><td style="border-bottom:6px double {INK};padding:38px 40px 26px;">
            <table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>
                <td style="font-family:{MONO};font-size:11px;font-weight:bold;letter-spacing:4px;color:{ACCENT};">&#9632; THE WEEKLY AI DISPATCH</td>
                <td align="right" style="font-family:{MONO};font-size:11px;letter-spacing:2px;color:{MUTED};">FREE EDITION</td>
            </tr></table>
            <div style="font-family:{SERIF};font-size:56px;font-weight:bold;line-height:1.0;color:{INK};padding:16px 0 14px;">Khabar <span style="color:{ACCENT};">AI</span></div>
            <div style="border-top:1px solid {INK};padding-top:9px;font-family:{MONO};font-size:11px;letter-spacing:2px;color:{INK};">
                {issue_date.upper()}
            </div>
        </td></tr>
"""

        # ---- This week in numbers (stat strip) ----
        total_stars = sum(int(r.get('stars', 0) or 0) for r in repos)
        all_categories = Counter()
        for p in papers:
            for c in p.get('categories', []):
                all_categories[c] += 1
        stats = []
        if papers:
            stats.append((str(len(papers)), "NEW PAPERS"))
        if repos:
            stats.append((str(len(repos)), "HOT REPOS"))
        if total_stars:
            stats.append((compact_num(total_stars), "STARS EARNED"))
        if all_categories:
            stats.append((str(len(all_categories)), "FIELDS"))
        if stats:
            cells = ""
            for j, (num, label) in enumerate(stats):
                border = f"border-left:1px solid {RULE};" if j else ""
                cells += (f'<td width="{100 // len(stats)}%" align="center" style="{border}padding:16px 6px;">'
                          f'<div style="font-family:{SERIF};font-size:32px;font-weight:bold;color:{INK};line-height:1;">{num}</div>'
                          f'<div style="font-family:{MONO};font-size:9px;font-weight:bold;letter-spacing:2px;color:{ACCENT};padding-top:7px;">{label}</div></td>')
            html += f"""
        <tr><td style="border-bottom:1px solid {INK};">
            <table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>{cells}</tr></table>
        </td></tr>
"""

        # ---- Big story ----
        if big_story.get("title"):
            story_title = escape(big_story.get("title", ""))
            story_text = escape(big_story.get("content", ""))
            drop_cap = ""
            if story_text:
                drop_cap = (f'<span style="float:left;font-family:{SERIF};font-size:56px;line-height:44px;'
                            f'font-weight:bold;color:{ACCENT};padding:5px 10px 0 0;">{story_text[0]}</span>')
                story_text = story_text[1:]
            source_link = ""
            if big_story.get("source"):
                source_link = f'<div style="padding-top:16px;">{mono_link(big_story["source"], "CONTINUE READING &#8599;")}</div>'
            html += f"""
        <tr><td style="padding:30px 40px 32px;">
            {eyebrow("&#9733; THE BIG STORY")}
            <div style="font-family:{SERIF};font-size:29px;font-weight:bold;line-height:1.15;color:{INK};padding-bottom:14px;">{story_title}</div>
            <div style="font-family:{SERIF};font-size:15px;line-height:1.7;color:{BODY_TXT};">{drop_cap}{story_text}</div>
            {source_link}
        </td></tr>
"""

        # ---- Research papers ----
        if papers:
            html += section_band("SECTION 01 &middot; LATEST RESEARCH", f"{len(papers[:5])} PAPERS")

            # FIG. 01 — papers by field
            if all_categories:
                top_cats = all_categories.most_common(5)
                max_count = top_cats[0][1]
                rows = "".join(
                    bar_row(cat, count, max_count, f"{count} PAPER{'S' if count != 1 else ''}",
                            color=ACCENT if k == 0 else INK)
                    for k, (cat, count) in enumerate(top_cats)
                )
                html += figure_box("FIG. 01 &mdash; THIS WEEK&rsquo;S PAPERS BY FIELD", rows)

            for i, paper in enumerate(papers[:5], 1):
                p_title = escape(paper.get('title', 'Untitled'))
                p_url = escape(paper.get('url', '#'), quote=True)
                authors = escape(', '.join(paper.get('authors', ['Unknown'])))
                published = escape(paper.get('published', ''))
                summary = escape(paper.get('summary', 'No summary available'))
                chips = ''.join(tag_chip(c) for c in paper.get('categories', [])[:3])
                pdf_link = f' &nbsp;&nbsp; {mono_link(paper["pdf_url"], "PDF &#8595;")}' if paper.get('pdf_url') else ''
                if i > 1:
                    html += dotted_rule()
                html += f"""
        <tr><td style="padding:26px 40px 26px;">
            <table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>
                <td width="58" valign="top" style="font-family:{SERIF};font-style:italic;font-size:38px;font-weight:bold;color:{ACCENT};line-height:1;">{i:02d}</td>
                <td valign="top">
                    <a href="{p_url}" target="_blank" style="font-family:{SERIF};font-size:19px;font-weight:bold;line-height:1.25;color:{INK};text-decoration:none;">{p_title}</a>
                    <div style="font-family:{MONO};font-size:11px;letter-spacing:1px;color:{MUTED};padding:8px 0 10px;">{authors} &nbsp;&middot;&nbsp; {published}</div>
                    <div style="font-family:{SERIF};font-size:14px;line-height:1.65;color:{BODY_TXT};padding-bottom:12px;">{summary}</div>
                    <div style="padding-bottom:14px;">{chips}</div>
                    <div>{mono_link(paper.get('url', '#'), "READ PAPER &#8599;")}{pdf_link}</div>
                </td>
            </tr></table>
        </td></tr>
"""

        # ---- GitHub repos (with OpenGraph card images) ----
        if repos:
            html += section_band("SECTION 02 &middot; TRENDING CODE", f"{len(repos[:5])} REPOS")

            # FIG. 02 — stars comparison
            shown = repos[:5]
            max_stars = max(int(r.get('stars', 0) or 0) for r in shown) or 1
            rows = "".join(
                bar_row((r.get('name') or '?')[:16].upper(), int(r.get('stars', 0) or 0), max_stars,
                        f"&#9733; {compact_num(r.get('stars', 0))}",
                        color=ACCENT if k == 0 else INK)
                for k, r in enumerate(shown)
            )
            html += figure_box("FIG. 02 &mdash; REPOSITORY STARS, THIS WEEK", rows)

            for i, repo in enumerate(shown, 1):
                full_name = repo.get('full_name', repo.get('name', ''))
                r_url = escape(repo.get('url', '#'), quote=True)
                r_name = escape(repo.get('name', 'Unnamed Repo'))
                r_desc = escape(repo.get('description') or 'No description available')
                og_image = escape(f"https://opengraph.githubassets.com/1/{full_name}", quote=True)
                chips = ''.join(tag_chip(t) for t in repo.get('topics', [])[:3])
                if i > 1:
                    html += dotted_rule()
                html += f"""
        <tr><td style="padding:26px 40px 26px;">
            <a href="{r_url}" target="_blank" style="text-decoration:none;">
                <img src="{og_image}" width="558" alt="{escape(full_name)} &mdash; GitHub repository" style="display:block;width:100%;height:auto;border:1px solid {INK};" />
            </a>
            <div style="padding-top:14px;">
                <a href="{r_url}" target="_blank" style="font-family:{SERIF};font-size:18px;font-weight:bold;color:{INK};text-decoration:none;">{r_name}</a>
            </div>
            <div style="font-family:{MONO};font-size:11px;letter-spacing:1px;color:{MUTED};padding:6px 0 8px;">&#9733; {repo.get('stars', 0):,} &nbsp;&middot;&nbsp; &#8916; {repo.get('forks', 0):,} FORKS &nbsp;&middot;&nbsp; {escape(str(repo.get('language', 'N/A'))).upper()}</div>
            <div style="font-family:{SERIF};font-size:14px;line-height:1.6;color:{BODY_TXT};padding-bottom:12px;">{r_desc}</div>
            <div style="padding-bottom:2px;">{chips}</div>
        </td></tr>
"""

        # ---- Products ----
        if products:
            html += section_band("SECTION 03 &middot; FRESH TOOLS", f"{len(products[:3])} LAUNCHES")

            # FIG. 03 — upvotes comparison
            shown_products = products[:3]
            max_votes = max(int(p.get('votes', 0) or 0) for p in shown_products) or 1
            rows = "".join(
                bar_row((p.get('name') or '?')[:16].upper(), int(p.get('votes', 0) or 0), max_votes,
                        f"&#9650; {compact_num(p.get('votes', 0))}",
                        color=ACCENT if k == 0 else INK)
                for k, p in enumerate(shown_products)
            )
            html += figure_box("FIG. 03 &mdash; LAUNCH UPVOTES", rows)

            for i, product in enumerate(shown_products, 1):
                if i > 1:
                    html += dotted_rule()
                html += f"""
        <tr><td style="padding:26px 40px 26px;">
            <table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>
                <td valign="top">
                    <a href="{escape(product.get('url', '#'), quote=True)}" target="_blank" style="font-family:{SERIF};font-size:19px;font-weight:bold;color:{INK};text-decoration:none;">{escape(product.get('name', 'Unnamed Product'))}</a>
                    <div style="font-family:{SERIF};font-style:italic;font-size:14px;color:{BODY_TXT};padding:6px 0 8px;">{escape(product.get('tagline', ''))}</div>
                </td>
                <td width="90" align="right" valign="top">
                    <span style="font-family:{MONO};font-size:12px;font-weight:bold;background-color:{INK};color:{PAPER};padding:5px 9px;white-space:nowrap;">&#9650; {product.get('votes', 0):,}</span>
                </td>
            </tr></table>
            <div style="font-family:{SERIF};font-size:14px;line-height:1.6;color:{BODY_TXT};padding-bottom:12px;">{escape((product.get('description') or '')[:200])}</div>
            <div>{mono_link(product.get('url', '#'), "CHECK IT OUT &#8599;")}</div>
        </td></tr>
"""

        # ---- Tweets ----
        if tweets:
            html += section_band("SECTION 04 &middot; HEARD ONLINE", f"{len(tweets[:3])} POSTS")
            for i, tweet in enumerate(tweets[:3], 1):
                if i > 1:
                    html += dotted_rule()
                html += f"""
        <tr><td style="padding:26px 40px 26px;">
            <div style="font-family:{SERIF};font-size:52px;line-height:0.5;color:{ACCENT};padding-top:10px;">&ldquo;</div>
            <div style="font-family:{SERIF};font-style:italic;font-size:17px;line-height:1.55;color:{INK};padding:4px 0 12px;">{escape(tweet.get('text', ''))}</div>
            <div style="font-family:{MONO};font-size:11px;letter-spacing:1px;color:{MUTED};padding-bottom:12px;">&mdash; {escape(tweet.get('author_name', 'Unknown'))} {escape(tweet.get('author', ''))} &nbsp;&middot;&nbsp; &#10084; {tweet.get('likes', 0):,} &nbsp;&middot;&nbsp; &#8635; {tweet.get('retweets', 0):,}</div>
            <div>{mono_link(tweet.get('url', '#'), "VIEW POST &#8599;")}</div>
        </td></tr>
"""

        # ---- Footer ----
        html += f"""
        <tr><td style="background-color:{INK};padding:30px 40px;">
            <div style="font-family:{MONO};font-size:11px;font-weight:bold;letter-spacing:3px;color:{PAPER};padding-bottom:10px;">THANKS FOR READING</div>
            <div style="font-family:{SERIF};font-style:italic;font-size:16px;color:{PAPER};padding-bottom:16px;">Stay curious, keep learning.</div>
            <div style="border-top:1px solid {MUTED};padding-top:14px;font-family:{MONO};font-size:10px;letter-spacing:1px;color:#A79C87;line-height:1.7;">
                KHABAR AI &mdash; YOUR WEEKLY SIGNAL IN THE NOISE<br>
                You&rsquo;re receiving this because you subscribed to Khabar AI.
            </div>
        </td></tr>

    </table>
    </td></tr>
    </table>
</body>
</html>
"""

        logger.info(f"Generated HTML newsletter ({len(html)} bytes)")

        return {
            "status": "success",
            "html": html,
            "size": len(html),
            "template": template
        }

    except Exception as e:
        logger.error(f"Failed to generate HTML: {str(e)}")
        return {
            "status": "error",
            "message": str(e)
        }


@mcp.tool()
@safe_api_call
def save_to_drive(
    content: str,
    filename: str,
    folder_id: Optional[str] = None
) -> Dict:
    """
    Save generated newsletter to Google Drive.
    
    Args:
        content: Newsletter HTML content
        filename: Name for the file
        folder_id: Target folder ID (uses NEWSLETTER_FOLDER_ID if not provided)
    
    Returns:
        File ID and link to the saved newsletter
    """
    if folder_id is None:
        folder_id = Config.NEWSLETTER_FOLDER_ID
    
    if not folder_id:
        return {
            "status": "error",
            "message": "No folder ID provided. Set NEWSLETTER_FOLDER_ID environment variable."
        }
    
    service = get_google_service('drive', 'v3')
    
    # Create file metadata
    file_metadata = {
        'name': filename,
        'parents': [folder_id],
        'mimeType': 'text/html'
    }
    
    # Create file content using MediaIoBaseUpload (fixed from MediaFileUpload)
    media = MediaIoBaseUpload(
        io.BytesIO(content.encode('utf-8')),
        mimetype='text/html',
        resumable=True
    )
    
    # Upload file
    file = service.files().create(
        body=file_metadata,
        media_body=media,
        fields='id, webViewLink'
    ).execute()
    
    logger.info(f"Saved newsletter to Drive: {filename}")
    
    return {
        "status": "success",
        "file_id": file['id'],
        "url": file['webViewLink'],
        "filename": filename
    }


@mcp.tool()
def export_newsletter(content: Dict, format: str = "html") -> Dict:
    """
    Export newsletter in multiple formats (HTML, Markdown, JSON).
    
    Args:
        content: Newsletter content
        format: Output format (html, markdown, json)
    
    Returns:
        Exported content in requested format
    """
    try:
        if format == "markdown":
            # Convert to markdown
            md = convert_to_markdown(content)
            return {
                "status": "success",
                "content": md,
                "format": "markdown",
                "size": len(md)
            }
        elif format == "json":
            json_content = json.dumps(content, indent=2)
            return {
                "status": "success",
                "content": json_content,
                "format": "json",
                "size": len(json_content)
            }
        else:
            # HTML is default
            return generate_html_newsletter(content)
    
    except Exception as e:
        logger.error(f"Export failed: {str(e)}")
        return {
            "status": "error",
            "message": str(e)
        }


def convert_to_markdown(content: Dict) -> str:
    """Helper function to convert newsletter content to Markdown"""
    metadata = content.get("metadata", {})
    sections = content.get("sections", {})
    
    md = f"""# {metadata.get('title', 'Newsletter')}
{metadata.get('date', '')}

---

"""
    
    # Big story
    big_story = sections.get("big_story", {})
    if big_story.get("title"):
        md += f"""## 🌟 This Week's Big Story

### {big_story['title']}

{big_story.get('content', '')}

{f"[Read More]({big_story['source']})" if big_story.get('source') else ''}

---

"""
    
    # Papers
    if sections.get("top_papers"):
        md += "## 📄 Top AI Research Papers\n\n"
        for i, paper in enumerate(sections["top_papers"][:5], 1):
            md += f"""### {i}. {paper.get('title', 'Untitled')}

**Authors:** {', '.join(paper.get('authors', ['Unknown']))}

{paper.get('summary', '')}

[Read Paper]({paper.get('url', '#')})

---

"""
    
    # Repos
    if sections.get("github_repos"):
        md += "## 💻 Trending GitHub Repositories\n\n"
        for repo in sections["github_repos"][:5]:
            md += f"""### ⭐ {repo.get('name', 'Unnamed')}

{repo.get('description', '')}

**Stats:** {repo.get('stars', 0):,} stars | {repo.get('forks', 0):,} forks | Language: {repo.get('language', 'N/A')}

[View Repository]({repo.get('url', '#')})

---

"""
    
    # Products
    if sections.get("ai_products"):
        md += "## 🛠️ New AI Products & Tools\n\n"
        for product in sections["ai_products"][:3]:
            md += f"""### {product.get('name', 'Unnamed')}

**{product.get('tagline', '')}**

{product.get('description', '')}

👍 {product.get('votes', 0):,} upvotes | [Check it out]({product.get('url', '#')})

---

"""
    
    md += "\n**Thanks for reading! 🙌**\n\n*Khabar AI — your weekly signal in the noise*\n"
    
    return md


# ==================== DISTRIBUTION PHASE TOOLS ====================

SUBSCRIBERS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "subscribers.txt")


def load_subscribers() -> List[str]:
    """Read subscriber emails from subscribers.txt (one per line, # for comments)"""
    if not os.path.exists(SUBSCRIBERS_FILE):
        return []
    with open(SUBSCRIBERS_FILE) as f:
        return [line.strip() for line in f if line.strip() and not line.strip().startswith("#")]


@mcp.tool()
def list_subscribers() -> Dict:
    """
    List all newsletter subscribers.

    Returns:
        List of subscriber email addresses
    """
    subscribers = load_subscribers()
    return {
        "status": "success",
        "count": len(subscribers),
        "subscribers": subscribers
    }


@mcp.tool()
def add_subscriber(email: str) -> Dict:
    """
    Add a subscriber email to the newsletter list.

    Args:
        email: Email address to add

    Returns:
        Updated subscriber count
    """
    email = email.strip().lower()
    if "@" not in email or "." not in email.split("@")[-1]:
        return {"status": "error", "message": f"Invalid email address: {email}"}

    subscribers = load_subscribers()
    if email in subscribers:
        return {"status": "success", "message": f"{email} is already subscribed", "count": len(subscribers)}

    with open(SUBSCRIBERS_FILE, "a") as f:
        f.write(email + "\n")

    logger.info(f"Added subscriber: {email}")
    return {"status": "success", "message": f"Added {email}", "count": len(subscribers) + 1}


@mcp.tool()
def remove_subscriber(email: str) -> Dict:
    """
    Remove a subscriber email from the newsletter list.

    Args:
        email: Email address to remove

    Returns:
        Updated subscriber count
    """
    email = email.strip().lower()
    subscribers = load_subscribers()
    if email not in subscribers:
        return {"status": "error", "message": f"{email} is not in the subscriber list"}

    subscribers.remove(email)
    with open(SUBSCRIBERS_FILE, "w") as f:
        f.write("\n".join(subscribers) + ("\n" if subscribers else ""))

    logger.info(f"Removed subscriber: {email}")
    return {"status": "success", "message": f"Removed {email}", "count": len(subscribers)}


@mcp.tool()
@safe_api_call
def send_newsletter_email(
    subject: str,
    html_content: Optional[str] = None,
    drive_file_id: Optional[str] = None,
    recipients: Optional[List[str]] = None,
    test_only: bool = False
) -> Dict:
    """
    Send the newsletter to subscribers via Gmail (as BCC to protect privacy).

    Args:
        subject: Email subject line
        html_content: Newsletter HTML (or use drive_file_id instead)
        drive_file_id: Google Drive file ID to send (e.g. from save_to_drive)
        recipients: Explicit recipient list (defaults to subscribers.txt)
        test_only: If True, send only to yourself as a preview

    Returns:
        Send confirmation with recipient count
    """
    if not html_content and not drive_file_id:
        return {"status": "error", "message": "Provide html_content or drive_file_id"}

    # Fetch HTML from Drive if a file ID was given
    if drive_file_id and not html_content:
        drive = get_google_service('drive', 'v3')
        html_content = drive.files().get_media(fileId=drive_file_id).execute().decode('utf-8')

    gmail = get_google_service('gmail', 'v1')
    sender = gmail.users().getProfile(userId='me').execute()['emailAddress']

    if test_only:
        recipients = [sender]
    elif recipients is None:
        recipients = load_subscribers()

    if not recipients:
        return {
            "status": "error",
            "message": "No recipients. Add subscribers with add_subscriber() or create subscribers.txt"
        }

    # Send in batches of 90 BCC recipients (Gmail limits recipients per message)
    sent_batches = 0
    for i in range(0, len(recipients), 90):
        batch = recipients[i:i + 90]
        message = MIMEText(html_content, 'html')
        message['To'] = sender
        message['Bcc'] = ", ".join(batch)
        message['Subject'] = subject

        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
        gmail.users().messages().send(userId='me', body={'raw': raw}).execute()
        sent_batches += 1

    logger.info(f"Newsletter sent to {len(recipients)} recipients in {sent_batches} batch(es)")

    return {
        "status": "success",
        "recipients_count": len(recipients),
        "batches": sent_batches,
        "from": sender,
        "subject": subject,
        "test_only": test_only
    }


# ==================== BATCH OPERATIONS ====================

@mcp.tool()
@safe_api_call
def fetch_all_research(config: Optional[Dict] = None) -> Dict:
    """
    Fetch all research content in one operation.
    
    Args:
        config: Optional configuration for research parameters
    
    Returns:
        Complete research data from all sources
    """
    if config is None:
        config = {
            "days_back": 7,
            "max_papers": 10,
            "max_repos": 10,
            "max_products": 10
        }
    
    results = {}
    errors = []
    
    logger.info("Starting batch research fetch...")
    
    # Fetch papers
    try:
        papers_result = search_arxiv_papers(
            max_results=config.get("max_papers", 10),
            days_back=config.get("days_back", 7)
        )
        if papers_result.get("status") == "success":
            results["papers"] = papers_result.get("papers", [])
        else:
            errors.append(f"Papers: {papers_result.get('message')}")
    except Exception as e:
        errors.append(f"Papers: {str(e)}")
    
    # Fetch repos
    try:
        repos_result = fetch_github_trending(timeframe="weekly")
        if repos_result.get("status") == "success":
            results["repositories"] = repos_result.get("repositories", [])
        else:
            errors.append(f"Repos: {repos_result.get('message')}")
    except Exception as e:
        errors.append(f"Repos: {str(e)}")
    
    # Fetch products (only if API key is configured)
    if Config.PRODUCT_HUNT_API_KEY:
        try:
            products_result = search_product_hunt(
                days_back=config.get("days_back", 7),
                limit=config.get("max_products", 10)
            )
            if products_result.get("status") == "success":
                results["products"] = products_result.get("products", [])
            else:
                errors.append(f"Products: {products_result.get('message')}")
        except Exception as e:
            errors.append(f"Products: {str(e)}")
    
    # Fetch tweets (only if API key is configured)
    if Config.TWITTER_BEARER_TOKEN:
        try:
            tweets_result = fetch_twitter_trends(
                days_back=config.get("days_back", 7)
            )
            if tweets_result.get("status") == "success":
                results["tweets"] = tweets_result.get("trending_tweets", [])
            else:
                errors.append(f"Tweets: {tweets_result.get('message')}")
        except Exception as e:
            errors.append(f"Tweets: {str(e)}")
    
    logger.info(f"Batch fetch complete: {len(results)} sources, {len(errors)} errors")
    
    return {
        "status": "success" if not errors else "partial",
        "research_data": results,
        "errors": errors,
        "sources_fetched": len(results),
        "config": config
    }


# ==================== PROMPTS ====================

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


# ==================== VALIDATION & STARTUP ====================

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


# ==================== MAIN ====================

if __name__ == "__main__":
    logger.info("Starting AI Newsletter MCP Server...")
    
    # Validate configuration
    if not validate_config():
        logger.error("Configuration validation failed. Please set required environment variables.")
        logger.error("Required: GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REFRESH_TOKEN")
    else:
        logger.info("All required configuration present")
    
    logger.info("Server ready to accept connections")
    mcp.run()