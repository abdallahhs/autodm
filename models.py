from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text
from sqlalchemy.sql import func
from database import Base


class Config(Base):
    __tablename__ = "configs"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String, unique=True, index=True, nullable=False)
    value = Column(Text, nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Campaign(Base):
    __tablename__ = "campaigns"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    post_id = Column(String, nullable=False)
    post_thumbnail = Column(Text, nullable=True)
    post_caption = Column(Text, nullable=True)
    keywords = Column(Text, nullable=False)          # comma-separated
    comment_reply = Column(Text, nullable=False)
    dm_message = Column(Text, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ProcessedComment(Base):
    __tablename__ = "processed_comments"

    id = Column(Integer, primary_key=True, index=True)
    comment_id = Column(String, unique=True, index=True, nullable=False)
    campaign_id = Column(Integer, nullable=True)
    commenter_id = Column(String, nullable=True)
    processed_at = Column(DateTime(timezone=True), server_default=func.now())


class ActionLog(Base):
    __tablename__ = "action_logs"

    id = Column(Integer, primary_key=True, index=True)
    campaign_id = Column(Integer, nullable=True)
    comment_id = Column(String, nullable=True)
    action = Column(String, nullable=False)   # "comment_reply", "dm_sent", "error"
    status = Column(String, nullable=False)   # "success", "failed"
    detail = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
