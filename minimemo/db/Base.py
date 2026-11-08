from sqlalchemy import text
from sqlalchemy.orm import DeclarativeBase

"""
数据库基础类
"""
class Base(DeclarativeBase):
    pass


"""
全文索引由 memory 表上的生成列 content_tsv 承担：
content_seg 是应用层用 jieba 切好的词串，
content_tsv 是 to_tsvector('simple', content_seg) 的 STORED 生成列，
GIN 索引在模型里声明，由 create_all / 迁移脚本建出来。

原文、情景记忆、语义记忆都是 memory 的子类，content 已上提到父表，
所以三者共用同一列索引，不需要各建各的。
"""


def init_tables(engine):
    """
    初始化数据库表
    """
    # 必须先把模型导进来，否则 Base.metadata 是空的，什么表都不会建
    # vector 类型依赖该扩展，建表前必须就位
    with engine.begin() as connection:
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

    Base.metadata.create_all(engine)
