"""Rate-limited, retrying wrapper around nba_api endpoints."""

import time
import random
import logging
from functools import wraps

from requests.exceptions import Timeout, ConnectionError

from config import NBA_API_SLEEP, NBA_API_RETRIES, NBA_API_TIMEOUT

logger = logging.getLogger("xfta.nba_client")

_last_call = 0.0


def _enforce_rate_limit():
    """Ensure minimum sleep between nba_api calls."""
    global _last_call
    now = time.monotonic()
    elapsed = now - _last_call
    if elapsed < NBA_API_SLEEP:
        time.sleep(NBA_API_SLEEP - elapsed)
    _last_call = time.monotonic()


def _backoff(attempt: int) -> float:
    """Exponential backoff with jitter."""
    base = 2 ** attempt
    jitter = random.uniform(0, 1)
    return base + jitter


def call_endpoint(endpoint_cls, *args, **kwargs):
    """Call an nba_api endpoint with rate limiting and retry logic.

    Parameters
    ----------
    endpoint_cls : class
        An nba_api endpoint class (e.g. ShotChartDetail).
    *args, **kwargs
        Passed to the endpoint constructor.

    Returns
    -------
    response object from the endpoint.
    """
    _enforce_rate_limit()
    timeout = kwargs.pop("_timeout", NBA_API_TIMEOUT)
    kwargs.setdefault("timeout", timeout)

    for attempt in range(NBA_API_RETRIES + 1):
        try:
            endpoint = endpoint_cls(*args, **kwargs)
            return endpoint
        except (Timeout, ConnectionError) as e:
            if attempt < NBA_API_RETRIES:
                wait = _backoff(attempt)
                logger.warning(
                    "%s on %s (attempt %d/%d), retrying in %.1fs",
                    type(e).__name__,
                    endpoint_cls.__name__,
                    attempt + 1,
                    NBA_API_RETRIES,
                    wait,
                )
                time.sleep(wait)
                _last_call = time.monotonic()  # rate limit already handled by backoff
            else:
                raise


def with_retry(func):
    """Decorator for functions that call nba_api endpoints directly."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        _enforce_rate_limit()
        for attempt in range(NBA_API_RETRIES + 1):
            try:
                result = func(*args, **kwargs)
                return result
            except (Timeout, ConnectionError) as e:
                if attempt < NBA_API_RETRIES:
                    wait = _backoff(attempt)
                    logger.warning(
                        "%s in %s (attempt %d/%d), retrying in %.1fs",
                        type(e).__name__,
                        func.__name__,
                        attempt + 1,
                        NBA_API_RETRIES,
                        wait,
                    )
                    time.sleep(wait)
                    _last_call = time.monotonic()
                else:
                    raise
        return None
    return wrapper
