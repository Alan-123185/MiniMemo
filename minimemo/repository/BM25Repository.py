from minimemo.config.data import settings
from sqlalchemy import text

"""
全文检索，返回 memory.id / memory_type 和一列相关度
pdb.score 越大越相关

索引建在 memory.content 上，用 ParadeDB 的 pdb.jieba 分词器，
中文在库内切，查询串不用再自己分词，「|||」会自动拿同一个分词器处理，
这里传进来的就是用户的原始文本

「|||」是 match disjunction，命中任一 token 即算命中；
要「所有 token 都命中」的话换成「&&&」

原文、情景记忆、语义记忆都是 memory 的子类，
内容都落在父表的 content 列上，所以这一个索引覆盖三者，
检索结果需要按 memory_type 再分流的话，在调用方做
"""
def fts_search(engine, match_expr: str, k: int = settings.TOP_K) -> list:
    sql = text("""
        SELECT m.id AS id, m.memory_type AS memory_type,
               pdb.score(m.id) AS score
        FROM memory m
        WHERE m.content ||| :m AND m.is_delete = false
        ORDER BY score DESC
        LIMIT :k
    """)
    with engine.connect() as conn:
        return conn.execute(sql, {"m": match_expr, "k": k}).fetchall()
