from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from db.connection import Base


class MomVote(Base):
    __tablename__ = "mom_vote"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    match_id: Mapped[int | None] = mapped_column(Integer, index=True)
    voter_name: Mapped[str | None] = mapped_column(String(100))
    voted_for: Mapped[str | None] = mapped_column(String(100))
    vote_type: Mapped[str | None] = mapped_column(String(20))
    timestamp: Mapped[object | None] = mapped_column(DateTime(timezone=True))


class VoteComment(Base):
    __tablename__ = "vote_comment"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    match_id: Mapped[int | None] = mapped_column(Integer, index=True)
    kakao_id: Mapped[str | None] = mapped_column(String(64))
    nickname: Mapped[str | None] = mapped_column(String(100))
    message: Mapped[str | None] = mapped_column(Text)
    timestamp: Mapped[object | None] = mapped_column(DateTime(timezone=True))


class AttendanceVote(Base):
    __tablename__ = "attendance_vote"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    match_id: Mapped[int | None] = mapped_column(Integer, index=True)
    kakao_id: Mapped[str | None] = mapped_column(String(64))
    nickname: Mapped[str | None] = mapped_column(String(100))
    response: Mapped[str | None] = mapped_column(String(20))
    timestamp: Mapped[object | None] = mapped_column(DateTime(timezone=True))


class Featured(Base):
    __tablename__ = "featured"

    player_name: Mapped[str] = mapped_column(String(100), primary_key=True)
    title_id1: Mapped[str | None] = mapped_column(String(50))
    title_id2: Mapped[str | None] = mapped_column(String(50))
    title_id3: Mapped[str | None] = mapped_column(String(50))


class PushSubscription(Base):
    __tablename__ = "push_subscription"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    endpoint: Mapped[str] = mapped_column(Text, unique=True)
    p256dh: Mapped[str | None] = mapped_column(Text)
    auth: Mapped[str | None] = mapped_column(Text)
