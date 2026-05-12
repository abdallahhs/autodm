import hashlib
import hmac
import json
import logging
import os

from fastapi import APIRouter, Depends, HTTPException, Request, Query
from sqlalchemy.orm import Session

from database import get_db
from models import Campaign, ProcessedComment, ActionLog, Config
import instagram as ig

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhook", tags=["webhook"])


def _get_config_value(db: Session, key: str, fallback_env: str = "") -> str:
    row = db.query(Config).filter(Config.key == key).first()
    if row and row.value:
        return row.value
    return os.getenv(fallback_env, "")


def _verify_signature(payload: bytes, signature_header: str, app_secret: str) -> bool:
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = hmac.new(
        app_secret.encode("utf-8"), payload, hashlib.sha256
    ).hexdigest()
    provided = signature_header[len("sha256="):]
    return hmac.compare_digest(expected, provided)


@router.get("")
async def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
):
    """Facebook webhook verification challenge."""
    verify_token = os.getenv("WEBHOOK_VERIFY_TOKEN", "")
    if hub_mode == "subscribe" and hub_verify_token == verify_token:
        logger.info("Webhook verified successfully.")
        return int(hub_challenge)
    logger.warning("Webhook verification failed.")
    raise HTTPException(status_code=403, detail="Verification failed")


@router.post("")
async def receive_webhook(request: Request, db: Session = Depends(get_db)):
    """Receive Instagram comment events and trigger automation."""
    raw_body = await request.body()
    signature = request.headers.get("X-Hub-Signature-256", "")

    app_secret = _get_config_value(db, "facebook_app_secret", "FACEBOOK_APP_SECRET")
    if app_secret:
        if not _verify_signature(raw_body, signature, app_secret):
            logger.warning("Invalid webhook signature — rejected.")
            raise HTTPException(status_code=403, detail="Invalid signature")

    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    logger.debug("Webhook payload: %s", payload)

    # Instagram sends: {"object": "instagram", "entry": [...]}
    if payload.get("object") != "instagram":
        return {"status": "ignored", "reason": "not instagram object"}

    access_token = _get_config_value(db, "access_token", "INSTAGRAM_ACCESS_TOKEN")
    ig_account_id = _get_config_value(db, "ig_account_id", "INSTAGRAM_BUSINESS_ACCOUNT_ID")

    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            if change.get("field") != "comments":
                continue
            value = change.get("value", {})
            await _handle_comment_event(value, access_token, ig_account_id, db)

    return {"status": "ok"}


async def _handle_comment_event(value: dict, access_token: str, ig_account_id: str, db: Session):
    comment_id = value.get("id")
    media_id = value.get("media", {}).get("id") or value.get("media_id")
    comment_text = value.get("text", "")
    commenter_id = value.get("from", {}).get("id")

    if not comment_id or not media_id:
        logger.warning("Comment event missing id or media_id: %s", value)
        return

    # Deduplication
    existing = db.query(ProcessedComment).filter(ProcessedComment.comment_id == comment_id).first()
    if existing:
        logger.info("Comment %s already processed, skipping.", comment_id)
        return

    # Find matching active campaign
    campaigns = db.query(Campaign).filter(
        Campaign.post_id == media_id,
        Campaign.is_active == True,
    ).all()

    matched_campaign = None
    for campaign in campaigns:
        keywords = [k.strip().lower() for k in campaign.keywords.split(",") if k.strip()]
        text_lower = comment_text.lower()
        if any(kw in text_lower for kw in keywords):
            matched_campaign = campaign
            break

    if not matched_campaign:
        logger.debug("No matching campaign for comment %s on post %s", comment_id, media_id)
        return

    # Mark as processed immediately (before API calls) to prevent double-fire
    processed = ProcessedComment(
        comment_id=comment_id,
        campaign_id=matched_campaign.id,
        commenter_id=commenter_id,
    )
    db.add(processed)
    db.commit()

    logger.info("Matched campaign '%s' for comment %s", matched_campaign.name, comment_id)

    # If commenter_id not in payload, fetch it
    if not commenter_id:
        commenter_id = await ig.get_ig_user_id_from_comment(comment_id, access_token)

    # 1) Reply to comment
    reply_result = await ig.reply_to_comment(comment_id, matched_campaign.comment_reply, access_token)
    _log_action(db, matched_campaign.id, comment_id, "comment_reply", reply_result)

    # 2) Send DM
    if commenter_id:
        dm_result = await ig.send_dm(commenter_id, matched_campaign.dm_message, ig_account_id, access_token)
        _log_action(db, matched_campaign.id, comment_id, "dm_sent", dm_result)
    else:
        logger.warning("Could not determine commenter ID for comment %s — DM skipped.", comment_id)
        _log_action(db, matched_campaign.id, comment_id, "dm_sent",
                    {"error": {"message": "Could not determine commenter ID"}})


def _log_action(db: Session, campaign_id: int, comment_id: str, action: str, result: dict):
    status = "failed" if "error" in result else "success"
    detail = json.dumps(result)
    log = ActionLog(
        campaign_id=campaign_id,
        comment_id=comment_id,
        action=action,
        status=status,
        detail=detail,
    )
    db.add(log)
    db.commit()
    if status == "failed":
        logger.error("Action '%s' failed: %s", action, result.get("error"))
    else:
        logger.info("Action '%s' succeeded.", action)
