from sqlalchemy import func, select
from sqlalchemy.orm import column_property

from app.models.comment import Comment
from app.models.like import PostLike
from app.models.post import Post
from app.models.user import User

# 게시글을 조회할 때 좋아요 수와 댓글 수를 상관 서브쿼리로 함께 가져온다.
# (모든 모델이 정의된 뒤에 연결해야 하므로 여기서 지정한다.)
Post.like_count = column_property(
    select(func.count())
    .where(PostLike.post_id == Post.id)
    .correlate_except(PostLike)
    .scalar_subquery()
)
Post.comment_count = column_property(
    select(func.count())
    .where(Comment.post_id == Post.id)
    .correlate_except(Comment)
    .scalar_subquery()
)

__all__ = ["Comment", "Post", "PostLike", "User"]
