from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Comment(Base):
    __tablename__ = "comments"
    __table_args__ = (
        # 게시글별 댓글을 작성 순으로 조회하므로 (post_id, created_at) 복합 인덱스를 둔다.
        Index("ix_comments_post_id_created_at", "post_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    content: Mapped[str] = mapped_column(Text)
    # 게시글이나 회원이 삭제되면 댓글도 DB에서 함께 삭제된다(ON DELETE CASCADE).
    post_id: Mapped[int] = mapped_column(ForeignKey("posts.id", ondelete="CASCADE"))
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    author: Mapped["User"] = relationship()  # noqa: F821
