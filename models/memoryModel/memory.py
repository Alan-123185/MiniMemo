import datetime
from typing import Literal
import uuid
from sqlalchemy import DateTime, ForeignKey, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column
from  config.data import settings
from  db.Base import Base


class Memory(Base):
    __tablename__ = "memory"

    id:Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"))
    content: Mapped[str]=mapped_column(nullable=False)
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


# 索引写在类外，只挂在 memory 这张表上
# 放在 __table_args__ 里的话，子类有各自的 tablename，这份 table_args 会被一起带过去，
# 于是在没有 content 列的 episodes 等表上再建一次
# content 交给 pdb.jieba 在库内分词，k1/b 是 BM25 参数，改了要重建索引才生效
Index(
    "ix_memory_content_bm25",
    Memory.__table__.c.id,
    text(f"(content::pdb.jieba('k1={settings.BM25_K1}','b={settings.BM25_B}'))"),
    postgresql_using="paradedb",
)
