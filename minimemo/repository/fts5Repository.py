from minimemo.config.data import settings
from sqlalchemy import text

"""
fts5 全文检索，返回 memory.id 和一列相关度
bm25 越小越相关，0 附近表示不相关
不传 table 是因为索引固定绑在 memory 上
"""
def fts_search(engine, match_expr: str, k: int = settings.TOP_K) -> list:
    sql = text("""
        SELECT m.id AS memory_id, bm25(memory_fts) AS score
        FROM memory_fts
        JOIN memory m ON m.rowid = memory_fts.rowid
        WHERE memory_fts MATCH :m AND m.is_delete = 0
        ORDER BY score ASC
        LIMIT :k
    """)
    with engine.connect() as conn:
        return conn.execute(sql, {"m": match_expr, "k": k}).fetchall()
