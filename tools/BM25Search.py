from common.bm25Result import bm25Result
from config.data import settings
from sqlalchemy import text

"""
全文检索，返回 memory.id / memory_type 和一列相关度
pdb.score 越大越相关

索引建在 memory.content 上，用 ParadeDB 的 pdb.jieba 分词器，
中文在库内切，查询串不用再自己分词，这里传进来的就是用户的原始文本

匹配用 match_disjunction，命中任一 token 即算命中。
不用「&&&」（match_conjunction，要求所有 token 都命中）：jieba 会把「的」「时」
「在」这类单字也切出来，要求它们也命中会直接把绝大多数题打成空候选

切出来的单字 token 在这里先剔掉再匹配：单字多是虚词，命中它不代表相关，
旧写法直接 `content ||| :m` 就是被这些 token 拉满 15 条候选的。
用 @@@ 而不是 |||，因为要把分词结果先过滤再构造 query，||| 只收文本

原文、情景记忆、语义记忆都是 memory 的子类，
内容都落在父表的 content 列上，所以这一个索引覆盖三者，
检索结果需要按 memory_type 再分流的话，在调用方做
"""
async def bm25_search(engine, match_expr: str, agent_id: str ) -> list:
    sql = text("""
        SELECT m.id AS id, m.memory_type AS memory_type,
               pdb.score(m.id) AS score
        FROM memory m
        WHERE m.content @@@ pdb.match_disjunction(ARRAY(
                  SELECT t FROM unnest(pdb.tokenize_jieba(CAST(:m AS pdb.jieba))) t
                  WHERE length(t) >= 2))
              AND m.is_delete = false AND m.agent_id = :agent_id
        ORDER BY score DESC
        LIMIT :k
    """)
    async with engine.connect() as conn:
        list=(await conn.execute(sql, {"m": match_expr, "agent_id": agent_id, "k": settings.BM25_CANDIDATE_LIMIT})).fetchall()
        return [bm25Result(memory_id=l[0], memory_type=l[1], score=l[2]) for l in list]
