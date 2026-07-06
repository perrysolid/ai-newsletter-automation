"""Shared decorators for rate limiting and API error handling."""

import logging
import time
from functools import wraps

import requests

logger = logging.getLogger(__name__)


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
