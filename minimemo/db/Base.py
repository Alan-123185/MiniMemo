from sqlalchemy import event, text
from sqlalchemy.orm import DeclarativeBase

"""
数据库基础类
"""
class Base(DeclarativeBase):
    pass

"""
创建 FTS表和触发器
"""
@event.listens_for(Base.metadata, "after_create")
def create_fts_tables(target, connection, **kw):
    # 1. 情景 FTS，绑 episodes
    connection.execute(text("""
        CREATE VIRTUAL TABLE IF NOT EXISTS episodes_fts USING fts5(
            content,
            content='episodes',
            content_rowid='id'
        )
    """))
    connection.execute(text("""
        CREATE TRIGGER IF NOT EXISTS episodes_ai AFTER INSERT ON episodes BEGIN
            INSERT INTO episodes_fts(rowid, content) VALUES (new.id, new.content);
        END;
    """))
    connection.execute(text("""
        CREATE TRIGGER IF NOT EXISTS episodes_ad AFTER DELETE ON episodes BEGIN
            INSERT INTO episodes_fts(episodes_fts, rowid, content)
            VALUES ('delete', old.id, old.content);
        END;
    """))
    connection.execute(text("""
        CREATE TRIGGER IF NOT EXISTS episodes_au AFTER UPDATE ON episodes BEGIN
            INSERT INTO episodes_fts(episodes_fts, rowid, content)
            VALUES ('delete', old.id, old.content);
           INSERT INTO episodes_fts(rowid, content) VALUES (new.id, new.content);
        END;
    """))

    # 2. 语义 FTS，绑 semantics
    connection.execute(text("""
        CREATE VIRTUAL TABLE IF NOT EXISTS semantic_fts USING fts5(
            content,
            content='semantics',
            content_rowid='id'
        )
    """))
    connection.execute(text("""
        CREATE TRIGGER IF NOT EXISTS semantics_ai AFTER INSERT ON semantics BEGIN
            INSERT INTO semantic_fts(rowid, content) VALUES (new.id, new.content);
        END;
    """))
    connection.execute(text("""
        CREATE TRIGGER IF NOT EXISTS semantics_ad AFTER DELETE ON semantics BEGIN
            INSERT INTO semantic_fts(semantic_fts, rowid, content)
            VALUES ('delete', old.id, old.content);
        END;
    """))
    connection.execute(text("""
        CREATE TRIGGER IF NOT EXISTS semantics_au AFTER UPDATE ON semantics BEGIN
            INSERT INTO semantic_fts(semantic_fts, rowid, content)
            VALUES ('delete', old.id, old.content);
            INSERT INTO semantic_fts(rowid, content) VALUES (new.id, new.content);
        END;
    """))