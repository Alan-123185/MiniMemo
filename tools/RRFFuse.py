from collections import defaultdict

def rrf_fuse(ranked_lists: list[list[str]], k: int = 60, top_n: int =10 ) -> list[str]:
    """ranked_lists: 多路检索结果，每路是按名次排好的 memory_id 列表"""
    scores = defaultdict(float)
    for ranked in ranked_lists:                 # 遍历每一路检索源
        for rank, doc_id in enumerate(ranked):  # rank 从 0 开始
            scores[doc_id] += 1 / (k + rank + 1)
    return sorted(scores, key=lambda doc_id: scores[doc_id], reverse=True)[:top_n]



# 用法
# bm25_ids   = [m.memory_id for m in bm25_results]      # BM25 排序结果
# vector_ids = [m.memory_id for m in vector_results]    # 向量排序结果
# final = rrf_fuse([bm25_ids, vector_ids], k=60, top_n=10)