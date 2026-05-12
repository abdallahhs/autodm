import httpx
import asyncio
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

GRAPH_API_BASE = "https://graph.facebook.com/v19.0"


def _get_token() -> str:
    """Get token from env or DB config (env takes priority for startup)."""
    return os.getenv("INSTAGRAM_ACCESS_TOKEN", "")


async def _request_with_backoff(
    method: str,
    url: str,
    max_retries: int = 3,
    **kwargs,
) -> dict:
    """Make an HTTP request with exponential backoff on rate limit / server errors."""
    delay = 1.0
    async with httpx.AsyncClient(timeout=30.0) as client:
        for attempt in range(max_retries):
            try:
                response = getattr(client, method)(url, **kwargs)
                if asyncio.iscoroutine(response):
                    response = await response
                else:
                    response = await getattr(client, method)(url, **kwargs)

                try:
                    data = response.json()
                except Exception:
                    data = {"error": {"message": f"Non-JSON response (HTTP {response.status_code})", "body": response.text[:200]}}
                logger.debug("Instagram API %s %s → %s", method.upper(), url, data)

                # Rate limit hit
                if response.status_code == 429 or (
                    isinstance(data, dict)
                    and data.get("error", {}).get("code") in (4, 17, 32, 613)
                ):
                    wait = delay * (2**attempt)
                    logger.warning("Rate limited. Retrying in %.1fs (attempt %d)", wait, attempt + 1)
                    await asyncio.sleep(wait)
                    continue

                return data

            except httpx.RequestError as exc:
                logger.error("Request error on attempt %d: %s", attempt + 1, exc)
                if attempt < max_retries - 1:
                    await asyncio.sleep(delay * (2**attempt))

    return {"error": {"message": "Max retries exceeded"}}


async def reply_to_comment(comment_id: str, message: str, access_token: str) -> dict:
    """Post a public reply to an Instagram comment."""
    url = f"{GRAPH_API_BASE}/{comment_id}/replies"
    result = await _request_with_backoff(
        "post", url,
        params={"access_token": access_token},
        json={"message": message},
    )
    if "error" in result:
        logger.error("reply_to_comment error: %s", result["error"])
    else:
        logger.info("Replied to comment %s", comment_id)
    return result


async def send_dm(instagram_user_id: str, message: str, ig_account_id: str, access_token: str) -> dict:
    """Send a private DM to a user via the Instagram Messaging API."""
    url = f"{GRAPH_API_BASE}/{ig_account_id}/messages"
    payload = {
        "recipient": {"id": instagram_user_id},
        "message": {"text": message},
    }
    result = await _request_with_backoff(
        "post", url,
        params={"access_token": access_token},
        json=payload,
    )
    if "error" in result:
        logger.error("send_dm error: %s", result["error"])
    else:
        logger.info("DM sent to user %s", instagram_user_id)
    return result


async def get_post_details(post_id: str, access_token: str) -> Optional[dict]:
    """
    Fetch thumbnail URL and caption for an Instagram media post.
    Returns dict with 'thumbnail_url', 'caption', 'media_type' or None on error.
    """
    url = f"{GRAPH_API_BASE}/{post_id}"
    result = await _request_with_backoff(
        "get", url,
        params={
            "fields": "id,caption,media_type,media_url,thumbnail_url,timestamp,permalink",
            "access_token": access_token,
        },
    )
    if "error" in result:
        logger.error("get_post_details error: %s", result.get("error"))
        return None

    thumbnail = result.get("thumbnail_url") or result.get("media_url")
    caption = result.get("caption", "")
    return {
        "id": result.get("id"),
        "thumbnail_url": thumbnail,
        "caption": caption[:200] if caption else "",
        "media_type": result.get("media_type", ""),
        "permalink": result.get("permalink", ""),
        "timestamp": result.get("timestamp", ""),
    }


async def get_ig_user_id_from_comment(comment_id: str, access_token: str) -> Optional[str]:
    """Fetch the Instagram User ID of the person who left a comment."""
    url = f"{GRAPH_API_BASE}/{comment_id}"
    result = await _request_with_backoff(
        "get", url,
        params={
            "fields": "id,from",
            "access_token": access_token,
        },
    )
    if "error" in result:
        logger.error("get_ig_user_id_from_comment error: %s", result.get("error"))
        return None
    from_data = result.get("from", {})
    return from_data.get("id")
