from datetime import datetime, timezone
from sqlalchemy import String, Integer, DateTime, ForeignKey, Float
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class GameResult(Base):
    __tablename__ = "game_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)

    game_type: Mapped[str] = mapped_column(String(20))
    score: Mapped[int] = mapped_column(Integer)
    xp_earned: Mapped[int] = mapped_column(Integer)
    duration: Mapped[float] = mapped_column(Float)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )