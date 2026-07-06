"""Research phase tools: arXiv, GitHub, Product Hunt, Twitter, Drive & Gmail."""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import arxiv
import requests

from .config import Config
from .google_client import get_google_service
from .server import mcp
from .utils import rate_limit, safe_api_call

logger = logging.getLogger(__name__)


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
