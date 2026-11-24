"""一次性统计四层召回，所有层共用同一次检索。

在项目根目录运行：
    python -m judgeMent.tests.layer_all --user-id USER --agent-id AGENT

每道题只做一次 embedding 和一次四路召回，再依次喂给四层统计，省掉重复检索。
层 1/2 按集合口径（任一路召回即算召回），层 3/4 按单一排序口径。
四层结果写进同一个日志文件，每行前缀标明所属层。
"""

import asyncio
from collections import Counter, defaultdict
from time import perf_counter

from loguru import logger
from openai import APIError

from judgeMent.tests import recall_common as common
from common.requestSchema.searchRequest import searchRequest
from config.data import settings
from db.session import create_session, engine
from repository.memoryRepository import memoryRepository
from tools.RRFFuse import rrf_fuse

LAYER = "all_layers"

STAGE1 = "层1·三路向量"
STAGE2 = "层2·三路向量+bm25"
STAGE3 = "层3·四路+RRF"
STAGE4 = "层4·四路+RRF+精排"
STAGES = (STAGE1, STAGE2, STAGE3, STAGE4)


def setup_log():
    """四层共用一个日志文件，每行用 extra 里的 stage 标明当前层。"""
    common.LOG_DIR.mkdir(parents=True, exist_ok=True)
    logger.remove()
    logger.add(
        common.LOG_DIR / (LAYER + "_{time:YYYY-MM-DD_HH-mm-ss}.log"),
        level="DEBUG",
        encoding="utf-8",
        format=lambda record: (
            "{time:HH:mm:ss} | {level: <7} | "
            + record["extra"].get("stage", "-")
            + " | {message}\n"
        ),
    )


def stage(name):
    """切换后续日志行的层标识。"""
    logger.configure(extra={"stage": name})


async def run_all(cases, user_id, agent_id):
    totals = {name: defaultdict(Counter) for name in STAGES}
    comparisons = []
    durations = []
    failed = 0
    top_n = settings.RRF_TOP_N
    try:
        async with create_session() as session:
            await common.validate_labels(session, cases, user_id, agent_id)
            repo = memoryRepository(session)
            service = common.make_service(session)

            stage(STAGE1)
            logger.info(f"{len(cases)} 题 | 四层一次统计 | RRF k={settings.RRF_K}，前 {top_n} 条")

            for case in cases:
                request = searchRequest(query=case["query"], user_id=user_id, agent_id=agent_id)
                # 四路只取一次，四层都从这一份结果里取数
                ranked = await common.route_rankings(service, request, common.ROUTES)
                ranked_lists = [ranked[route] for route in common.ROUTES]
                final_ids = rrf_fuse(ranked_lists=ranked_lists, k=settings.RRF_K, top_n=top_n)

                stage(STAGE1)
                common.report_multi(case, ranked, common.VECTOR_ROUTES, totals[STAGE1])

                stage(STAGE2)
                common.report_multi(case, ranked, common.ROUTES, totals[STAGE2])

                stage(STAGE3)
                common.report_single(case, ranked_lists, final_ids, settings.RRF_K, top_n, totals[STAGE3])

                stage(STAGE4)
                memories = await repo.search_memory(final_ids)
                before_ids = [memory.id for memory in memories]
                start = perf_counter()
                try:
                    async with asyncio.timeout(30):
                        reranked = await service.fine_ranking(request, memories)
                except (APIError, TimeoutError) as exc:
                    failed += 1
                    logger.warning(f"精排失败（{type(exc).__name__}），本题按 RRF 排序统计")
                    common.report_single(case, ranked_lists, final_ids, settings.RRF_K, top_n, totals[STAGE4])
                    continue
                if memories:
                    durations.append(perf_counter() - start)
                after_ids = [memory.id for memory in reranked]
                common.report_single(case, ranked_lists, after_ids, settings.RRF_K, top_n, totals[STAGE4])

                relevant = case["relevant"]
                comparisons.append((
                    common.ranking_scores(before_ids, relevant),
                    common.ranking_scores(after_ids, relevant),
                ))
                before_ranks, after_ranks = common.ranks(before_ids), common.ranks(after_ids)
                logger.info("  标注名次（RRF → 精排）")
                for memory_id, memory_type in relevant.items():
                    logger.info(f"    {memory_type} {memory_id} "
                                f"{before_ranks.get(memory_id, '-')} → {after_ranks.get(memory_id, '-')}")
    finally:
        await engine.dispose()

    stage(STAGE1)
    common.log_multi_summary(totals[STAGE1], len(cases))
    stage(STAGE2)
    common.log_multi_summary(totals[STAGE2], len(cases))
    stage(STAGE3)
    common.log_single_summary(totals[STAGE3], top_n)
    stage(STAGE4)
    common.log_single_summary(totals[STAGE4], top_n)
    common.log_rerank_summary(comparisons, durations, failed)


def main():
    parser = common.build_parser(__doc__)
    args = parser.parse_args()
    setup_log()
    cases = common.load_cases(args.cases)
    try:
        common.run(lambda: run_all(cases, args.user_id, args.agent_id))
    except (OSError, ValueError) as exc:
        parser.exit(1, f"评测失败：{exc}\n")


if __name__ == "__main__":
    main()
