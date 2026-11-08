import datetime
from typing import Literal
import uuid
from sqlalchemy import Computed, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column, validates
from  minimemo.db.Base import Base
from minimemo.tools.textSegment import segment


class Memory(Base):
    __tablename__ = "memory"

    id:Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"))
    content: Mapped[str]=mapped_column(nullable=False)
    # jieba 切好的词串，供下面那列生成 tsvector 用，PG 的 simple 配置切不动中文
    content_seg: Mapped[str]=mapped_column(Text, nullable=False, default="")
    # to_tsvector('simple', ...) 必须是 immutable 表达式才能做生成列，
    # 而 to_tsvector(regconfig, text) 恰好是 immutable 的，可以写在生成列里
    content_tsv: Mapped[str]=mapped_column(
        TSVECTOR,
        Computed("to_tsvector('simple', content_seg)", persisted=True),
        nullable=True,
    )
    create_time: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.now)
    update_time: Mapped[datetime.datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.datetime.now(),
        onupdate=lambda: datetime.datetime.now(),
    )
    is_delete:Mapped[bool] = mapped_column(default=False, nullable=False)



    memory_type: Mapped[Literal["origin","episodic","semantic"]] = mapped_column(index=True)   # 鉴别器

    __mapper_args__ = {
        "polymorphic_on": "memory_type",
        "polymorphic_identity": "base",
    }

    @validates("content")
    def _segment_content(self, key, value):
        """
        content 一变就同步切好词串
        三个子类都通过 content= 构造，挂在父类这一处就够了
        批量 update 走的是 query(...).update()，不经过这里，调用方需自行维护 content_seg
        """
        self.content_seg = segment(value)
        return value


# 索引写在类外，只挂在 memory 这张表上
# 放在 __table_args__ 里的话，子类有各自的 tablename，这份 table_args 会被一起带过去，
# 于是在没有 content_tsv 列的 episodes 等表上再建一次同名索引
Index("ix_memory_content_tsv", Memory.__table__.c.content_tsv, postgresql_using="gin")
