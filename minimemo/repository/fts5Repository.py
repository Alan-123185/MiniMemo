from minimemo.config.data import settings
from minimemo.tools.textSegment import segment
from sqlalchemy import text

"""
全文检索，返回 memory.id / memory_type 和一列相关度
ts_rank 越大越相关

查询串与入库时一样先过 jieba 再交给 plainto_tsquery：
入库是 to_tsvector('simple', content_seg)，查询也必须走 simple 配置才切得一致。
用 plainto_tsquery 而不是 to_tsquery，是因为后者会把串里的标点当成 tsquery 语法，
jieba 切出的「：」「，」这类 token 会让它直接报语法错

原文、情景记忆、语义记忆都是 memory 的子类，
内容都落在父表的 content 列上，所以这一列索引覆盖三者，
检索结果需要按 memory_type 再分流的话，在调用方做

TODO:这个到时候要改 成BM25
"""
def fts_search(engine, match_expr: str, k: int = settings.TOP_K) -> list:
    sql = text("""
        SELECT m.id AS id, m.memory_type AS memory_type,
               ts_rank(m.content_tsv, query) AS score
        FROM memory m, plainto_tsquery('simple', :m) AS query
        WHERE m.content_tsv @@ query AND m.is_delete = false
        ORDER BY score DESC
        LIMIT :k
    """)
    with engine.connect() as conn:
        return conn.execute(sql, {"m": segment(match_expr), "k": k}).fetchall()
