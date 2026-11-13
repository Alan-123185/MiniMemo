from sqlalchemy import text
from sqlalchemy.orm import DeclarativeBase

"""
数据库基础类
"""
class Base(DeclarativeBase):
    pass


"""
全文索引是 memory 表上的一个 ParadeDB 索引（ix_memory_content_bm25），
建在 content 列上，用 pdb.jieba 分词器，中文在库内切，
打分走 BM25（pdb.score），由 pg_search 扩展提供，索引在模型里声明。

原文、情景记忆、语义记忆都是 memory 的子类，content 已上提到父表，
所以三者共用同一列索引，不需要各建各的。
"""


async def init_tables(engine):
    """
    初始化数据库表
    """
    # 必须先把模型导进来，否则 Base.metadata 是空的，什么表都不会建
    # vector 是向量列类型，pg_search 提供全文索引与 BM25，两者建表前都要就位
    async with engine.begin() as connection:
        await connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await connection.execute(text("CREATE EXTENSION IF NOT EXISTS pg_search CASCADE"))

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
