from sqlalchemy import event, text
from sqlalchemy.orm import DeclarativeBase

"""
数据库基础类
"""
class Base(DeclarativeBase):
    pass


"""
全文索引 FTS5，绑 memory 表
memory 是 joined 继承的父表，content 已上提到这里，
原文、情景记忆、语义记忆都是它的子类，
所以三者的内容会自动进入同一张索引，不需要各建各的。

memory.id 是 UUID 字符串，而 fts5 的 rowid 必须是整数，
因此走 external content 模式，content_rowid 指向 memory 的隐式整数 rowid，
检索时再 join 回 memory 取真正的 id。
"""
_FTS_DDL = (
    """
    CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(
        content,
        content='memory',
        content_rowid='rowid'
    )
    """,
    """
    CREATE TRIGGER IF NOT EXISTS memory_ai AFTER INSERT ON memory BEGIN
        INSERT INTO memory_fts(rowid, content) VALUES (new.rowid, new.content);
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS memory_ad AFTER DELETE ON memory BEGIN
        INSERT INTO memory_fts(memory_fts, rowid, content)
        VALUES ('delete', old.rowid, old.content);
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS memory_au AFTER UPDATE ON memory BEGIN
        INSERT INTO memory_fts(memory_fts, rowid, content)
        VALUES ('delete', old.rowid, old.content);
        INSERT INTO memory_fts(rowid, content) VALUES (new.rowid, new.content);
    END
    """,
)


def _fts_exists(connection) -> bool:
    return connection.execute(
        text("SELECT 1 FROM sqlite_master WHERE type='table' AND name='memory_fts'")
    ).first() is not None


def _memory_exists(connection) -> bool:
    return connection.execute(
        text("SELECT 1 FROM sqlite_master WHERE type='table' AND name='memory'")
    ).first() is not None


def create_fts_tables(connection):
    """
    建 FTS 表与触发器
    外部内容表只存索引不存原文，已经存在的 memory 行需要 rebuild 才能被检索到
    """
    # metadata 为空时 create_all 不会建 memory，after_create 却照样触发，
    # 此时建触发器会直接报错，所以这里先确认宿主表在
    if not _memory_exists(connection):
        return
    is_new = not _fts_exists(connection)
    for ddl in _FTS_DDL:
        connection.execute(text(ddl))
    if is_new:
        connection.execute(text("INSERT INTO memory_fts(memory_fts) VALUES('rebuild')"))


def drop_fts_tables(connection):
    """
    拆掉 FTS 虚拟表与触发器，downgrade 时用
    先删触发器再删虚拟表，否则虚拟表的影子表会留下
    """
    for suffix in ("ai", "ad", "au"):
        connection.execute(text(f"DROP TRIGGER IF EXISTS memory_{suffix}"))
    connection.execute(text("DROP TABLE IF EXISTS memory_fts"))


@event.listens_for(Base.metadata, "after_create")
def _on_after_create(target, connection, **kw):
    """
    建完表之后顺带把 FTS 建上
    """
    create_fts_tables(connection)


def init_tables(engine):
    """
    初始化数据库表
    """
    # 必须先把模型导进来，否则 Base.metadata 是空的，什么表都不会建
    import minimemo.models  # noqa: F401

    Base.metadata.create_all(engine)
    # 表已经存在时 create_all 不产生任何 DDL，after_create 也就不会触发，
    # 这里补一次，保证 FTS 与触发器一定就位
    with engine.begin() as connection:
        create_fts_tables(connection)
