from minimemo.config.data import settings
from sqlalchemy import text

"""
fts5算法查询关键词 取前k条结果，返回rowid和相似度
越相关越小  越不相关越接近0
"""
def fts_search(engine, table: str, match_expr: str, k: int = settings.TOP_K) -> list:
    sql = text(f"""
        SELECT rowid, bm25({table}) AS s
        FROM {table}
        WHERE {table} MATCH :m
        ORDER BY s ASC
        LIMIT :k
    """)
    with engine.connect() as conn:
        return conn.execute(sql, {"m": match_expr, "k": k}).fetchall()