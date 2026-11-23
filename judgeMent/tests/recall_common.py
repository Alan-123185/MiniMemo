"""四层召回评测的公共部分。

四层各自一个文件，都能单独在 judgeMent 目录下运行：
    python -m tests.layer1_vector --user-id USER --agent-id AGENT
    python -m tests.layer2_bm25   --user-id USER --agent-id AGENT
    python -m tests.layer3_rrf    --user-id USER --agent-id AGENT
    python -m tests.layer4_rerank --user-id USER --agent-id AGENT

层 1、层 2 是多路并列，没有共同排序，按集合口径统计：一条标注被任一路召回即算
召回，被任一路排进前 5 即算该题命中；不产出 nDCG@5 这类依赖单一排序的指标。
层 3、层 4 有 RRF 或精排产出的单一排序，按排序口径统计。
日志写到 judgeMent/testLog/，文件名和每行都带层标识。
"""

import argparse
import asyncio
import json
import sys
from collections import Counter, defaultdict
from math import ceil, log2
from pathlib import Path
from statistics import median
from time import perf_counter

from loguru import logger
from openai import APIError
from sqlalchemy import select

from common.requestSchema.searchRequest import searchRequest
from config.data import settings
from config.modelConfig import modelPool
from db.session import create_session, engine
from models.agent import Agent
from models.memoryModel.memory import Memory
from repository.embeddingRepository import embeddingRepository
from repository.memoryRepository import memoryRepository
from repository.userRepository import userRepository
from service.modelService import modelService
from service.searchService import searchService
from tools.RRFFuse import rrf_fuse


# 三路向量召回，等级相同，不分主次
VECTOR_ROUTES = ("origin", "episodic", "semantic")
# 四路：三路向量 + bm25
ROUTES = ("bm25", *VECTOR_ROUTES)

TESTS_DIR = Path(__file__).resolve().parent
# 题集和日志都放在 judgeMent 下
DEFAULT_CASES = TESTS_DIR.parent / "question" / "recall_cases.json"
LOG_DIR = TESTS_DIR.parent / "testLog"

GROUP_NAMES = ("全部", *VECTOR_ROUTES)


def load_cases(path):
    """读题集并校验格式。标注本身是否有效留给连库时核对。"""
    cases = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(cases, list) or not cases:
        raise ValueError("题集需要是非空 JSON 数组")
    for number, case in enumerate(cases, start=1):
        if not isinstance(case, dict) or not isinstance(case.get("query"), str) or not case["query"].strip():
            raise ValueError(f"第 {number} 题缺少非空 query")
        relevant = case.get("relevant")
        if not isinstance(relevant, dict) or not relevant or any(
            not memory_id.strip() or memory_type not in VECTOR_ROUTES
            for memory_id, memory_type in relevant.items()
        ):
            raise ValueError(f"第 {number} 题的 relevant 应为 {{memory_id: memory_type}}")
    return cases


def ranks(memory_ids):
    """id 列表 → {id: 名次}，名次从 1 开始。"""
    return {memory_id: rank for rank, memory_id in enumerate(memory_ids, start=1)}


def best_ranks(ranked_lists):
    """多路并列时取每条记忆在各路里的最好名次。"""
    best = {}
    for ranked in ranked_lists:
        for rank, memory_id in enumerate(ranked, start=1):
            if memory_id not in best or rank < best[memory_id]:
                best[memory_id] = rank
    return best


def ranking_scores(memory_ids, relevant):
    """单一排序的指标，只看前 10 位。"""
    hits = {}
    for rank, memory_id in enumerate(memory_ids[:10], start=1):
        if memory_id in relevant:
            hits.setdefault(memory_id, rank)
    top_5 = [rank for rank in hits.values() if rank <= 5]
    ideal_dcg = sum(1 / log2(rank + 1) for rank in range(1, min(len(relevant), 5) + 1))
    return {
        "hit1": 1 in top_5,
        "hit5": bool(top_5),
        "evidence5": len(top_5),
        "evidence10": len(hits),
        "ndcg5": sum(1 / log2(rank + 1) for rank in top_5) / ideal_dcg,
    }


def setup_log(slug, name):
    """把日志落到 judgeMent/testLog，去掉默认的 stderr sink，只留文件。"""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logger.remove()
    logger.add(
        LOG_DIR / (slug + "_{time:YYYY-MM-DD_HH-mm-ss}.log"),
        level="DEBUG",
        encoding="utf-8",
        format="{time:HH:mm:ss} | {level: <7} | " + name + " | {message}",
    )


def make_service(session):
    """建搜索服务，四层的召回都走同一个实例。"""
    return searchService(
        embedding_repository=embeddingRepository(session),
        memory_repository=memoryRepository(session),
        user_repository=userRepository(session),
    )


async def validate_labels(session, cases, user_id, agent_id):
    """先核对标注，避免把样例 ID、旧 ID 或标错的类型算成召回失败。"""
    agent = await session.get(Agent, agent_id)
    if agent is None or agent.user_id != user_id:
        raise ValueError("找不到该用户下的 Agent，请使用内部 agent_id")
    target_ids = {memory_id for case in cases for memory_id in case["relevant"]}
    rows = await session.execute(
        select(Memory.id, Memory.memory_type).where(
            Memory.id.in_(target_ids),
            Memory.agent_id == agent_id,
            Memory.is_delete.is_(False),
        )
    )
    actual_types = dict(rows.all())
    for case in cases:
        for memory_id, memory_type in case["relevant"].items():
            if actual_types.get(memory_id) != memory_type:
                raise ValueError(f"标注 {memory_id} 不存在、已删除、不属于该 Agent 或类型不符")


async def route_rankings(service, request, routes):
    """取指定各路的排序。三路向量共用一次查询向量，bm25 单独走全文检索。"""
    ranked = {}
    vector_routes = [route for route in routes if route in VECTOR_ROUTES]
    if vector_routes:
        config = await service.user_repository.get_models(request.user_id)
        model = modelPool(**config.model_dump(exclude_none=True))
        query_embedding = await modelService.embedding(request.query, model.embedding)
    for route in routes:
        if route in VECTOR_ROUTES:
            # 复用生产服务里的单路向量召回，评测和线上不各走一套实现
            ranked[route] = await service._search_memory_L1(request, query_embedding, route)
        elif route == "bm25":
            ranked[route] = await searchService._search_bm25(request)
    return ranked


def report_multi(case, ranked, routes, totals):
    """层 1/2：打印单题多路明细，按集合口径累计。"""
    ranked_lists = [ranked[route] for route in routes]
    route_ranks = [ranks(ranked_list) for ranked_list in ranked_lists]
    best = best_ranks(ranked_lists)

    logger.info(case["query"])
    logger.info(f"  各路候选数 {[len(ranked_list) for ranked_list in ranked_lists]}，去重后 {len(best)}")

    top_5_types = set()
    for memory_id, memory_type in case["relevant"].items():
        found = memory_id in best
        positions = " ".join(
            f"{route}={position.get(memory_id, '-')}"
            for route, position in zip(routes, route_ranks)
        )
        outcome = f"召回到（最好名次 {best[memory_id]}）" if found else "各路均未召回"
        logger.info(f"  {memory_type} {memory_id} | {positions} | {outcome}")

        for group in ("全部", memory_type):
            totals[group]["标注"] += 1
            totals[group]["召回"] += found
        if found and best[memory_id] <= 5:
            top_5_types.update(("全部", memory_type))

    for group in {"全部", *case["relevant"].values()}:
        totals[group]["题目"] += 1
        totals[group]["前5命中"] += group in top_5_types


def report_single(case, ranked_lists, final_ids, k, top_n, totals):
    """层 3/4：打印单题单一排序明细，按排序口径累计。"""
    candidates = {memory_id for ranked in ranked_lists for memory_id in ranked}
    # 生产返回的是截断后的结果，这里重算一次不截断的 RRF，才能分清「没召回」和「被截掉」
    full_ranks = ranks(rrf_fuse(ranked_lists, k=k, top_n=len(candidates)))
    final_ranks = ranks(final_ids)
    route_ranks = [ranks(ranked) for ranked in ranked_lists]

    logger.info(case["query"])
    logger.info(f"  四路候选数 {[len(ranked) for ranked in ranked_lists]}，"
                f"去重后 {len(candidates)}，最终取 {len(final_ids)}")

    top_5_types = set()
    totals["全部"]["超过上限的题目"] += len(candidates) > top_n
    for memory_id, memory_type in case["relevant"].items():
        rrf_rank = full_ranks.get(memory_id)
        final_rank = final_ranks.get(memory_id)
        if final_rank is not None:
            outcome = f"进入前 {top_n}"
        elif rrf_rank is not None:
            outcome = f"被前 {top_n} 截掉"
        else:
            outcome = "四路均未召回"
        positions = " ".join(
            f"{route}={position.get(memory_id, '-')}"
            for route, position in zip(ROUTES, route_ranks)
        )
        logger.info(f"  {memory_type} {memory_id} | {positions} | RRF={rrf_rank or '-'} | {outcome}")

        for group in ("全部", memory_type):
            totals[group]["标注"] += 1
            totals[group]["召回"] += rrf_rank is not None
            totals[group]["保留"] += final_rank is not None
        if final_rank is not None and final_rank <= 5:
            top_5_types.update(("全部", memory_type))

    for group in {"全部", *case["relevant"].values()}:
        totals[group]["题目"] += 1
        totals[group]["前5命中"] += group in top_5_types


def log_multi_summary(totals, case_count):
    logger.info(f"汇总（{case_count} 题，多路并列，任一路召回即算召回）")
    for group in GROUP_NAMES:
        counts = totals[group]
        expected = counts["标注"]
        if not expected:
            continue
        recalled = counts["召回"]
        hits = counts["前5命中"]
        group_cases = counts["题目"]
        logger.info(
            f"  {group}: 召回 {recalled}/{expected} ({recalled / expected:.1%}) | "
            f"Hit@5（按题）{hits}/{group_cases} ({hits / group_cases:.1%})"
        )


def log_single_summary(totals, top_n):
    case_count = totals["全部"]["题目"]
    cutoff = totals["全部"]["超过上限的题目"]
    logger.info(f"汇总（{case_count} 题，{cutoff} 题的去重候选超过 {top_n}）")
    for group in GROUP_NAMES:
        counts = totals[group]
        expected = counts["标注"]
        if not expected:
            continue
        recalled = counts["召回"]
        kept = counts["保留"]
        hits_at_5 = counts["前5命中"]
        group_cases = counts["题目"]
        logger.info(
            f"  {group}: 候选召回率 {recalled}/{expected} ({recalled / expected:.1%}) | "
            f"Recall@{top_n} {kept}/{expected} ({kept / expected:.1%}) | "
            f"Hit@5（按题）{hits_at_5}/{group_cases} ({hits_at_5 / group_cases:.1%}) | "
            f"截掉 {recalled - kept} 条标注"
        )


def log_rerank_summary(comparisons, durations, failed):
    count = len(comparisons)
    logger.info(f"粗排和精排对比（同候选 {count} 题，精排失败 {failed} 题）")
    if not comparisons:
        return

    logger.info("  阶段         Hit@1  Hit@5   证据@5  证据@10  nDCG@5")
    for label, results in zip(("RRF", "精排"), zip(*comparisons)):
        totals = Counter()
        for scores in results:
            totals.update(scores)
        logger.info(f"  {label}    {totals['hit1']:>4}/{count:<3} "
                    f"{totals['hit5']:>4}/{count:<3} {totals['evidence5']:>6} "
                    f"{totals['evidence10']:>8} {totals['ndcg5'] / count:>8.4f}")

    improved = sum(after["ndcg5"] > before["ndcg5"] for before, after in comparisons)
    regressed = sum(after["ndcg5"] < before["ndcg5"] for before, after in comparisons)
    logger.info(f"  逐题 nDCG@5 上升 {improved}，持平 {count - improved - regressed}，下降 {regressed}")
    if durations:
        p95 = sorted(durations)[ceil(0.95 * len(durations)) - 1]
        logger.info(f"  精排耗时（{len(durations)} 次成功调用）P50={median(durations):.2f}s，P95={p95:.2f}s")


async def run_multi(cases, user_id, agent_id, routes):
    """层 1/2 的骨架：取多路排序，按集合口径统计。"""
    totals = defaultdict(Counter)
    try:
        async with create_session() as session:
            await validate_labels(session, cases, user_id, agent_id)
            service = make_service(session)
            logger.info(f"{len(cases)} 题 | 各路 {'、'.join(routes)} | 集合口径（任一路召回即算召回）")
            for case in cases:
                request = searchRequest(query=case["query"], user_id=user_id, agent_id=agent_id)
                ranked = await route_rankings(service, request, routes)
                report_multi(case, ranked, routes, totals)
    finally:
        await engine.dispose()
    log_multi_summary(totals, len(cases))


async def run_single(cases, user_id, agent_id, *, rerank=False):
    """层 3/4 的骨架：四路 → RRF，按单一排序统计；rerank 时再走一遍精排并对比。"""
    totals = defaultdict(Counter)
    comparisons = []
    durations = []
    failed = 0
    top_n = settings.RRF_TOP_N
    try:
        async with create_session() as session:
            await validate_labels(session, cases, user_id, agent_id)
            repo = memoryRepository(session)
            service = make_service(session)
            logger.info(f"{len(cases)} 题 | RRF k={settings.RRF_K}，前 {top_n} 条"
                        + (" | 叠加精排对比" if rerank else ""))
            for case in cases:
                request = searchRequest(query=case["query"], user_id=user_id, agent_id=agent_id)
                ranked = await route_rankings(service, request, ROUTES)
                ranked_lists = [ranked[route] for route in ROUTES]
                final_ids = rrf_fuse(ranked_lists=ranked_lists, k=settings.RRF_K, top_n=top_n)

                if not rerank:
                    report_single(case, ranked_lists, final_ids, settings.RRF_K, top_n, totals)
                    continue

                memories = await repo.search_memory(final_ids)
                before_ids = [memory.id for memory in memories]
                start = perf_counter()
                try:
                    async with asyncio.timeout(30):
                        reranked = await service.fine_ranking(request, memories)
                except (APIError, TimeoutError) as exc:
                    failed += 1
                    logger.warning(f"精排失败（{type(exc).__name__}），本题保留召回统计")
                    report_single(case, ranked_lists, final_ids, settings.RRF_K, top_n, totals)
                    continue
                if memories:
                    durations.append(perf_counter() - start)
                after_ids = [memory.id for memory in reranked]
                # 本层统计口径跟着精排后的最终排序走
                report_single(case, ranked_lists, after_ids, settings.RRF_K, top_n, totals)
                relevant = case["relevant"]
                comparisons.append((
                    ranking_scores(before_ids, relevant),
                    ranking_scores(after_ids, relevant),
                ))
                before_ranks, after_ranks = ranks(before_ids), ranks(after_ids)
                logger.info("  标注名次（RRF → 精排）")
                for memory_id, memory_type in relevant.items():
                    logger.info(f"    {memory_type} {memory_id} "
                                f"{before_ranks.get(memory_id, '-')} → {after_ranks.get(memory_id, '-')}")
    finally:
        await engine.dispose()
    log_single_summary(totals, top_n)
    if rerank:
        log_rerank_summary(comparisons, durations, failed)


def build_parser(description):
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES, help="标注题集的 JSON 文件")
    parser.add_argument("--user-id", required=True)
    parser.add_argument("--agent-id", required=True, help="数据库中的内部 Agent ID")
    return parser


def run(coro_factory):
    # Windows 上 psycopg 的异步驱动不能用默认的 ProactorEventLoop
    loop = asyncio.SelectorEventLoop if sys.platform == "win32" else None
    with asyncio.Runner(loop_factory=loop) as runner:
        runner.run(coro_factory())
