"""扫描 RRF_TOP_N，用 nDCG@5 作为选 N 的标准。

在项目根目录运行：
    python -m judgeMent.tools.get_TOP_N --user-id USER --agent-id AGENT

N 决定「有多少候选能进精排」，这个数只影响精排后的排序，不影响纯 RRF 的名次
（前 5 名永远是前 5 名），所以这里统计的是精排排序的 nDCG@5。

重排只对 (query, doc) 逐条打分，同一条候选的分数不随同批其他候选变化，因此每道题
只对全部候选精排一次，再按各个 N 从合并后的排序里筛出子集，即可还原「精排前 N 条」
的结果，不必为每个 N 重调一次精排。
"""

import asyncio
from collections import defaultdict
from statistics import mean

from loguru import logger
from openai import APIError

from common.requestSchema.searchRequest import searchRequest
from config.data import settings
from db.session import create_session, engine
from judgeMent.tests import recall_common as common
from repository.memoryRepository import memoryRepository
from tools.RRFFuse import rrf_fuse

LAYER = "get_top_n"
NAME = "TOP_N 扫描"

# 逐个 N 试：10、15、20 …… 到候选上限
STEP = 5
START = 10
STOP = 45


async def run_scan(cases, user_id, agent_id):
    limits = list(range(START, STOP + 1, STEP))
    ndcg = defaultdict(list)
    skipped = 0
    try:
        async with create_session() as session:
            await common.validate_labels(session, cases, user_id, agent_id)
            repo = memoryRepository(session)
            service = common.make_service(session)
            logger.info(f"{len(cases)} 题 | 扫描 N={limits} | RRF k={settings.RRF_K}，现用 N={settings.RRF_TOP_N}")

            for index, case in enumerate(cases, start=1):
                request = searchRequest(query=case["query"], user_id=user_id, agent_id=agent_id)
                ranked = await common.route_rankings(service, request, common.ROUTES)
                ranked_lists = [ranked[route] for route in common.ROUTES]
                candidates = {memory_id for ranked_list in ranked_lists for memory_id in ranked_list}
                full_order = rrf_fuse(ranked_lists=ranked_lists, k=settings.RRF_K, top_n=len(candidates))

                memories = await repo.search_memory(full_order)
                try:
                    async with asyncio.timeout(30):
                        reranked = await service.fine_ranking(request, memories)
                except (APIError, TimeoutError) as exc:
                    skipped += 1
                    logger.warning(f"第 {index} 题精排失败（{type(exc).__name__}），整题跳过")
                    continue

                # 全量精排的次序，任意子集的相对次序都跟它一致
                order = [memory.id for memory in reranked]
                relevant = case["relevant"]
                detail = []
                for limit in limits:
                    keep = set(full_order[:limit])
                    picked = [memory_id for memory_id in order if memory_id in keep]
                    value = common.ranking_scores(picked, relevant)["ndcg5"]
                    ndcg[limit].append(value)
                    detail.append(f"N{limit}={value:.3f}")
                logger.info(f"  [{index}/{len(cases)}] " + " ".join(detail))
    finally:
        await engine.dispose()

    count = len(ndcg[limits[0]])
    logger.info(f"汇总（{count} 题，跳过 {skipped} 题，同候选，仅精排后排序口径）")
    logger.info("  N     平均 nDCG@5")
    for limit in limits:
        values = ndcg[limit]
        if not values:
            continue
        mark = "   ← 现用" if limit == settings.RRF_TOP_N else ""
        logger.info(f"  {limit:<4}  {mean(values):.4f}{mark}")
    if count:
        best = max(limits, key=lambda limit: mean(ndcg[limit]))
        logger.info(f"  nDCG@5 最高的 N：{best}（{mean(ndcg[best]):.4f}）")


def main():
    parser = common.build_parser(__doc__)
    args = parser.parse_args()
    common.setup_log(LAYER, NAME)
    cases = common.load_cases(args.cases)
    try:
        common.run(lambda: run_scan(cases, args.user_id, args.agent_id))
    except (OSError, ValueError) as exc:
        parser.exit(1, f"评测失败：{exc}\n")


if __name__ == "__main__":
    main()
