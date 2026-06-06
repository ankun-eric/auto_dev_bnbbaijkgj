"""
益智乐园（Brain Game）数据模型。

本模块将 brain_game 相关 ORM 模型从 api 层抽取到 models 层，
供 main.py 启动迁移和种子数据初始化使用。

表：
- brain_game_regions：行政区划缓存表（高德 API 同步 + 内置种子数据）
- brain_game_scores：用户数学游戏成绩
- brain_game_challenges：组队挑战
- brain_game_challenge_members：挑战成员及成绩
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    Integer,
    String,
    Text,
)

from app.core.database import Base


class BrainGameRegion(Base):
    """行政区划缓存表（高德 API 同步 + 内置种子数据）"""

    __tablename__ = "brain_game_regions"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, autoincrement=True)
    adcode = Column(String(12), nullable=False, index=True, comment="高德行政区划编码")
    name = Column(String(128), nullable=False, comment="名称")
    level = Column(String(16), nullable=False, comment="级别：province/city/district/street")
    parent_adcode = Column(String(12), nullable=True, index=True, comment="父级 adcode")
    center = Column(String(64), nullable=True, comment="中心经纬度")
    synced_at = Column(DateTime, default=datetime.utcnow, comment="同步时间")


class BrainGameScore(Base):
    """用户数学游戏成绩"""

    __tablename__ = "brain_game_scores"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)
    difficulty = Column(String(16), nullable=False, comment="难度: basic/mid/hard")
    score = Column(Integer, nullable=False, comment="得分")
    right_count = Column(Integer, nullable=False, comment="答对题数")
    total_count = Column(Integer, nullable=False, comment="总题数")
    time_seconds = Column(Integer, nullable=False, comment="用时(秒)")
    province = Column(String(64), nullable=True)
    city = Column(String(64), nullable=True)
    district = Column(String(64), nullable=True)
    street = Column(String(128), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class BrainGameChallenge(Base):
    """组队挑战"""

    __tablename__ = "brain_game_challenges"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(16), nullable=False, unique=True, index=True, comment="挑战编号")
    creator_id = Column(Integer, nullable=False, index=True)
    difficulty = Column(String(16), nullable=False, comment="难度")
    team_size = Column(Integer, nullable=False, comment="队伍人数上限")
    status = Column(String(16), nullable=False, default="active", comment="active/done/expired")
    total_score = Column(Integer, nullable=True, default=0, comment="队伍总分")
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True, comment="超时时间(2小时)")


class BrainGameChallengeMember(Base):
    """挑战成员及成绩"""

    __tablename__ = "brain_game_challenge_members"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, autoincrement=True)
    challenge_id = Column(Integer, nullable=False, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    score = Column(Integer, nullable=False, default=0)
    right_count = Column(Integer, nullable=False, default=0)
    time_seconds = Column(Integer, nullable=False, default=0)
    done = Column(Boolean, nullable=False, default=False)
    joined_at = Column(DateTime, default=datetime.utcnow)
    finished_at = Column(DateTime, nullable=True)
