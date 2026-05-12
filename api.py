import logging
import os
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models import Campaign, Config, ActionLog, ProcessedComment
import instagram as ig

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["api"])


# ─── Pydantic Schemas ────────────────────────────────────────────────────────

class ConfigIn(BaseModel):
    access_token: str
    ig_account_id: str
    facebook_app_secret: Optional[str] = None


class ConfigOut(BaseModel):
    access_token_set: bool
    ig_account_id: Optional[str]
    facebook_app_secret_set: bool


class CampaignIn(BaseModel):
    name: str
    post_id: str
    post_thumbnail: Optional[str] = None
    post_caption: Optional[str] = None
    keywords: str       # comma-separated
    comment_reply: str
    dm_message: str
    is_active: bool = True


class CampaignOut(BaseModel):
    id: int
    name: str
    post_id: str
    post_thumbnail: Optional[str]
    post_caption: Optional[str]
    keywords: str
    comment_reply: str
    dm_message: str
    is_active: bool

    class Config:
        from_attributes = True


class LogOut(BaseModel):
    id: int
    campaign_id: Optional[int]
    comment_id: Optional[str]
    action: str
    status: str
    detail: Optional[str]
    created_at: Optional[str]

    class Config:
        from_attributes = True


# ─── Config Endpoints ─────────────────────────────────────────────────────────

def _set_config(db: Session, key: str, value: str):
    row = db.query(Config).filter(Config.key == key).first()
    if row:
        row.value = value
    else:
        db.add(Config(key=key, value=value))
    db.commit()


def _get_config(db: Session, key: str, env_fallback: str = "") -> Optional[str]:
    row = db.query(Config).filter(Config.key == key).first()
    if row and row.value:
        return row.value
    return os.getenv(env_fallback) or None


@router.post("/config")
def save_config(data: ConfigIn, db: Session = Depends(get_db)):
    _set_config(db, "access_token", data.access_token)
    _set_config(db, "ig_account_id", data.ig_account_id)
    if data.facebook_app_secret:
        _set_config(db, "facebook_app_secret", data.facebook_app_secret)
    return {"status": "saved"}


@router.get("/config", response_model=ConfigOut)
def get_config(db: Session = Depends(get_db)):
    token = _get_config(db, "access_token", "INSTAGRAM_ACCESS_TOKEN")
    ig_id = _get_config(db, "ig_account_id", "INSTAGRAM_BUSINESS_ACCOUNT_ID")
    secret = _get_config(db, "facebook_app_secret", "FACEBOOK_APP_SECRET")
    return ConfigOut(
        access_token_set=bool(token),
        ig_account_id=ig_id,
        facebook_app_secret_set=bool(secret),
    )


# ─── Post Preview ─────────────────────────────────────────────────────────────

@router.get("/post-preview")
async def post_preview(post_id: str, db: Session = Depends(get_db)):
    token = _get_config(db, "access_token", "INSTAGRAM_ACCESS_TOKEN")
    if not token:
        raise HTTPException(status_code=400, detail="Access token not configured")
    details = await ig.get_post_details(post_id, token)
    if not details:
        raise HTTPException(status_code=404, detail="Post not found or API error")
    return details


# ─── Campaign Endpoints ───────────────────────────────────────────────────────

@router.get("/campaigns", response_model=List[CampaignOut])
def list_campaigns(db: Session = Depends(get_db)):
    return db.query(Campaign).order_by(Campaign.created_at.desc()).all()


@router.post("/campaigns", response_model=CampaignOut)
def create_campaign(data: CampaignIn, db: Session = Depends(get_db)):
    campaign = Campaign(**data.dict())
    db.add(campaign)
    db.commit()
    db.refresh(campaign)
    return campaign


@router.put("/campaigns/{campaign_id}", response_model=CampaignOut)
def update_campaign(campaign_id: int, data: CampaignIn, db: Session = Depends(get_db)):
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    for field, value in data.dict().items():
        setattr(campaign, field, value)
    db.commit()
    db.refresh(campaign)
    return campaign


@router.patch("/campaigns/{campaign_id}/toggle")
def toggle_campaign(campaign_id: int, db: Session = Depends(get_db)):
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    campaign.is_active = not campaign.is_active
    db.commit()
    return {"id": campaign.id, "is_active": campaign.is_active}


@router.delete("/campaigns/{campaign_id}")
def delete_campaign(campaign_id: int, db: Session = Depends(get_db)):
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    db.delete(campaign)
    db.commit()
    return {"status": "deleted"}


# ─── Logs & Stats ─────────────────────────────────────────────────────────────

@router.get("/logs")
def get_logs(limit: int = 50, db: Session = Depends(get_db)):
    logs = db.query(ActionLog).order_by(ActionLog.created_at.desc()).limit(limit).all()
    return [
        {
            "id": l.id,
            "campaign_id": l.campaign_id,
            "comment_id": l.comment_id,
            "action": l.action,
            "status": l.status,
            "detail": l.detail,
            "created_at": str(l.created_at),
        }
        for l in logs
    ]


@router.get("/stats")
def get_stats(db: Session = Depends(get_db)):
    total_campaigns = db.query(Campaign).count()
    active_campaigns = db.query(Campaign).filter(Campaign.is_active == True).count()
    total_processed = db.query(ProcessedComment).count()
    total_replies = db.query(ActionLog).filter(ActionLog.action == "comment_reply", ActionLog.status == "success").count()
    total_dms = db.query(ActionLog).filter(ActionLog.action == "dm_sent", ActionLog.status == "success").count()
    total_errors = db.query(ActionLog).filter(ActionLog.status == "failed").count()
    return {
        "total_campaigns": total_campaigns,
        "active_campaigns": active_campaigns,
        "total_processed": total_processed,
        "total_replies": total_replies,
        "total_dms": total_dms,
        "total_errors": total_errors,
    }
