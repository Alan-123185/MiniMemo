from minimemo.config.data import settings
from sqlalchemy import text

"""
fts5 全文检索，返回 memory.id 和一列相关度
bm25 越小越相关，0 附近表示不相关

原文、情景记忆、语义记忆都是 memory 的子类，
内容都落在父表的 content 列上，所以这一张索引覆盖三者，
检索结果需要按 memory_type 再分流的话，在调用方做
"""
def fts_search(engine, match_expr: str, k: int = settings.TOP_K) -> list:
    sql = text("""
        SELECT m.id AS id, m.memory_type AS memory_type, bm25(memory_fts) AS score
        FROM memory_fts
        JOIN memory m ON m.rowid = memory_fts.rowid
        WHERE memory_fts MATCH :m AND m.is_delete = 0
        ORDER BY score ASC
        LIMIT :k
    """)
    with engine.connect() as conn:
        return conn.execute(sql, {"m": match_expr, "k": k}).fetchall()
