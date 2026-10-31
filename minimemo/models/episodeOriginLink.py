from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from minimemo.db.Base import Base


"""
情景记忆与原文的关联表
一条情景记忆由一批原文抽出，一条原文也可能参与多条情景记忆，
所以是多对多，用复合主键防重复边
"""
class episodeOriginLink(Base):
    __tablename__ = "episode_origin_link"

    episode_id: Mapped[str] = mapped_column(
        ForeignKey("episodes.id"), primary_key=True
    )
    origin_content_id: Mapped[str] = mapped_column(
        ForeignKey("origin_content.id"), primary_key=True
    )
