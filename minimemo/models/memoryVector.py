import datetime
import uuid
from pgvector.sqlalchemy import HALFVEC
from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from  minimemo.config.data import settings
from  minimemo.db.Base import Base


class memoryVector(Base):
    __tablename__ = "memory_vector"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    memory_id :Mapped[str] = mapped_column(ForeignKey("memory.id"))
    embedding :Mapped[list[float]] = mapped_column(HALFVEC(settings.EMBEDDING_DIM), nullable=False)  # 维度由配置指定，需与远端 embedding 模型一致
    create_time: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.now)
    embedding_model : Mapped[str] = mapped_column(nullable=False)
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"),nullable=False)
    # 这个表的索引是 hnsw，查询时用的是 vector_cosine_ops，cosine 距离越小越相似
    __table_args__ = (
        Index(
            "ix_memory_vector_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "halfvec_cosine_ops"},
        ),
    )
