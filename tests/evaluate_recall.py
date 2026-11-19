"""评测四路召回、RRF 粗排和精排。从项目根目录运行。

查看离线样例：python -m tests.evaluate_recall --demo
评测已有数据：python -m tests.evaluate_recall --user-id USER --agent-id AGENT --cases tests/recall_cases.json
对比粗排和精排：在真实评测命令后加 --rerank，使用当前用户配置的模型处理候选正文。
比较全量与 top25、扫描窗口并做两折验证：python -m tests.evaluate_rerank_study，沿用真实评测参数。

AGENT 是数据库中的内部 ID。relevant 的键为预先标注的真实 memory_id，
值为记忆类型。真实评测读取已有记忆，每道题按现有服务调用一次查询向量化。
"""

# 导入命令行参数解析模块
import argparse
# 导入异步运行工具
import asyncio
# 导入 JSON 解析模块
import json
import sys
# 导入用于统计指标的容器
from collections import Counter, defaultdict
from math import ceil, log2
# 导入路径类型
from pathlib import Path
from statistics import median
from time import perf_counter
# 导入用于捕获调用参数的 mock 工具
from unittest.mock import patch

# 导入 RRF 融合函数
from tools.RRFFuse import rrf_fuse


# 定义可以评测的记忆类型
MEMORY_TYPES = ("origin", "episodic", "semantic")
# 定义可以评测的记忆类型
ROUTES = ("bm25", *MEMORY_TYPES)
# 定位默认离线题集
EXAMPLE_CASES = Path(__file__).with_name("recall_cases.example.json")


# 定义加载并校验题集的函数
def load_cases(path):
    # 读取并解析题集文件
    cases = json.loads(path.read_text(encoding="utf-8"))
    # 检查对象类型和必填字段
    if not isinstance(cases, list) or not cases:
        # 输入不合法时报告错误
        raise ValueError("题集需要是非空 JSON 数组")
    # 逐题检查题集
    for number, case in enumerate(cases, start=1):
        # 检查对象类型和必填字段
        if not isinstance(case, dict) or not isinstance(case.get("query"), str) or not case["query"].strip():
            # 输入不合法时报告错误
            raise ValueError(f"第 {number} 题缺少非空 query")
        # 取出题目的相关记忆标注
        relevant = case.get("relevant")
        # 检查对象类型和必填字段
        if not isinstance(relevant, dict) or not relevant or any(
            # 检查记忆 ID 和类型是否合法
            not memory_id.strip() or memory_type not in MEMORY_TYPES
            # 遍历标注的记忆
            for memory_id, memory_type in relevant.items()
        ):
            # 输入不合法时报告错误
            raise ValueError(f"第 {number} 题的 relevant 应为 {{memory_id: memory_type}}")
    # 返回校验通过的题集
    return cases


# 定义生成记忆排名的函数
def ranks(memory_ids):
    # 为记忆 ID 分配从 1 开始的排名
    return {memory_id: rank for rank, memory_id in enumerate(memory_ids, start=1)}


# 定义输出单题结果并累计指标的函数
def report_case(case, ranked_lists, final_ids, k, top_n, totals):
    # 遍历标注的记忆
    candidates = {memory_id for ranked in ranked_lists for memory_id in ranked}
    # 计算不截断时的完整 RRF 排名
    full_ranks = ranks(rrf_fuse(ranked_lists, k=k, top_n=len(candidates)))
    # 记录实际结果中的排名
    final_ranks = ranks(final_ids)
    # 建立各召回路的排名映射
    route_ranks = [ranks(ranked) for ranked in ranked_lists]
    # 输出评测结果或运行信息
    print(f"\n{case['query']}")
    # 输出评测结果或运行信息
    print(f"  四路候选数 {[len(ranked) for ranked in ranked_lists]}，去重后 {len(candidates)}，RRF 取 {len(final_ids)}")

    # 确定本题参与统计的分组
    evaluated_types = {"全部", *case["relevant"].values()}
    # 记录前五名命中的分组
    top_5_types = set()
    # 更新该分组的统计数据
    totals["全部"]["超过上限的题目"] += len(candidates) > top_n
    # 遍历标注的记忆
    for memory_id, memory_type in case["relevant"].items():
        # 查找标注记忆的 RRF 名次
        rrf_rank = full_ranks.get(memory_id)
        # 查找标注记忆的最终名次
        final_rank = final_ranks.get(memory_id)
        # 查找标注记忆的最终名次
        if final_rank is not None:
            outcome = f"进入前 {top_n}"
        # 查找标注记忆的 RRF 名次
        elif rrf_rank is not None:
            outcome = f"被前 {top_n} 截掉"
        else:
            outcome = "四路均未召回"

        # 拼接记忆在各路召回中的位次
        positions = " ".join(
            f"{route}={position.get(memory_id, '-')}"
            for route, position in zip(ROUTES, route_ranks)
        )
        # 输出评测结果或运行信息
        print(f"  {memory_type} {memory_id} | {positions} | RRF={rrf_rank or '-'} | {outcome}")

        for group in ("全部", memory_type):
            # 更新该分组的统计数据
            totals[group]["标注"] += 1
            # 查找标注记忆的 RRF 名次
            totals[group]["召回"] += rrf_rank is not None
            # 查找标注记忆的最终名次
            totals[group]["保留"] += final_rank is not None
        # 查找标注记忆的最终名次
        if final_rank is not None and final_rank <= 5:
            # 记录前五名命中的分组
            top_5_types.update(("全部", memory_type))

    # 确定本题参与统计的分组
    for group in evaluated_types:
        # 更新该分组的统计数据
        totals[group]["题目"] += 1
        # 记录前五名命中的分组
        totals[group]["前5命中"] += group in top_5_types


# 定义输出总体评测指标的函数
def report_summary(totals, top_n):
    # 更新该分组的统计数据
    case_count = totals["全部"]["题目"]
    # 更新该分组的统计数据
    cutoff_case_count = totals["全部"]["超过上限的题目"]
    # 输出评测结果或运行信息
    print(f"\n汇总（{case_count} 题，{cutoff_case_count} 题的去重候选超过 {top_n}）")
    for group in ("全部", *MEMORY_TYPES):
        # 更新该分组的统计数据
        counts = totals[group]
        # 读取标注总数
        expected = counts["标注"]
        if expected:
            # 读取被召回的标注数
            recalled = counts["召回"]
            # 读取进入最终结果的标注数
            kept = counts["保留"]
            # 读取前五名命中数
            hits_at_5 = counts["前5命中"]
            # 读取总题目数
            group_case_count = counts["题目"]
            # 输出评测结果或运行信息
            print(
                f"  {group}: 候选召回率 {recalled}/{expected} ({recalled / expected:.1%}) | "
                f"Recall@{top_n} {kept}/{expected} ({kept / expected:.1%}) | "
                # 读取总题目数
                f"Hit@5（按题）{hits_at_5}/{group_case_count} ({hits_at_5 / group_case_count:.1%}) | "
                f"截掉 {recalled - kept} 条标注"
            )


def ranking_scores(memory_ids, relevant):
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


def report_rerank_summary(comparisons, durations, failed):
    count = len(comparisons)
    print(f"\n粗排和精排对比（同候选 {count} 题，精排失败 {failed} 题）")
    if not comparisons:
        return

    print("  阶段         Hit@1  Hit@5   证据@5  证据@10  nDCG@5")
    for label, results in zip(("RRF", "精排"), zip(*comparisons)):
        totals = Counter()
        for scores in results:
            totals.update(scores)
        print(f"  {label}    {totals['hit1']:>4}/{count:<3} "
              f"{totals['hit5']:>4}/{count:<3} {totals['evidence5']:>6} "
              f"{totals['evidence10']:>8} {totals['ndcg5'] / count:>8.4f}")

    improved = sum(after["ndcg5"] > before["ndcg5"] for before, after in comparisons)
    regressed = sum(after["ndcg5"] < before["ndcg5"] for before, after in comparisons)
    print(f"  逐题 nDCG@5 上升 {improved}，持平 {count - improved - regressed}，下降 {regressed}")
    if durations:
        p95 = sorted(durations)[ceil(0.95 * len(durations)) - 1]
        print(f"  精排耗时（{len(durations)} 次成功调用）P50={median(durations):.2f}s，P95={p95:.2f}s")


# 定义使用样例排名的离线演示
def run_demo(cases):
    # 输出评测结果或运行信息
    print("离线演示：各路名次由样例预先指定，只演示 RRF 和评测统计。")
    # 使用配置中的返回数量上限
    k, top_n = 60, 50
    totals = defaultdict(Counter)
    for case in cases:
        # 取出四路排名输入
        ranked_lists = [case["demo_rankings"][route] for route in ROUTES]
        # 执行实际的 RRF 预排序
        final_ids = rrf_fuse(ranked_lists, k=k, top_n=top_n)
        # 取出四路排名输入
        report_case(case, ranked_lists, final_ids, k, top_n, totals)
    report_summary(totals, top_n)


# 定义连接真实数据库的评测流程
async def run_live(cases, user_id, agent_id, *, rerank=False):
    from openai import APIError
    # 导入当前流程所需的依赖
    from sqlalchemy import select

    # 导入当前流程所需的依赖
    from common.requestSchema.searchRequest import searchRequest
    # 导入当前流程所需的依赖
    from config.data import settings
    # 导入当前流程所需的依赖
    from db.session import create_session, engine
    # 导入当前流程所需的依赖
    from models.agent import Agent
    # 导入当前流程所需的依赖
    from models.memoryModel.memory import Memory
    # 导入当前流程所需的依赖
    from repository.embeddingRepository import embeddingRepository
    # 导入当前流程所需的依赖
    from repository.memoryRepository import memoryRepository
    # 导入当前流程所需的依赖
    from repository.userRepository import userRepository
    # 导入当前流程所需的依赖
    from service.searchService import searchService

    totals = defaultdict(Counter)
    comparisons = []
    durations = []
    failed = 0
    try:
        async with create_session() as session:
            agent = await session.get(Agent, agent_id)
            if agent is None or agent.user_id != user_id:
                # 输入不合法时报告错误
                raise ValueError("找不到该用户下的 Agent，请使用内部 agent_id")

            # 先核对标注，避免把样例 ID、旧 ID 或标错的类型算成召回失败。
            # 遍历标注的记忆
            target_ids = {memory_id for case in cases for memory_id in case["relevant"]}
            # 执行数据库查询
            rows = await session.execute(
                select(Memory.id, Memory.memory_type).where(
                    # 收集所有标注的记忆 ID
                    Memory.id.in_(target_ids),
                    Memory.agent_id == agent_id,
                    Memory.is_delete.is_(False),
                )
            )
            # 遍历标注的记忆
            actual_types = {memory_id: memory_type for memory_id, memory_type in rows}
            for case in cases:
                # 遍历标注的记忆
                for memory_id, memory_type in case["relevant"].items():
                    # 将查询结果转为类型映射
                    if actual_types.get(memory_id) != memory_type:
                        # 输入不合法时报告错误
                        raise ValueError(f"标注 {memory_id} 不存在、已删除、不属于该 Agent 或类型不符")

            # 创建搜索服务
            memory_repo = memoryRepository(session)
            service = searchService(
                embedding_repository=embeddingRepository(session),
                memory_repository=memory_repo,
                user_repository=userRepository(session),
            )
            # 使用配置中的返回数量上限
            top_n = settings.RRF_TOP_N
            # 输出评测结果或运行信息
            print(f"真实召回：RRF k={settings.RRF_K}，前 {top_n} 条")
            for case in cases:
                # 构造当前题目的搜索请求
                request = searchRequest(query=case["query"], user_id=user_id, agent_id=agent_id)
                # 记录生产 RRF 的输入，实际融合仍由原函数执行。
                # 捕获 RRF 输入但不改变其执行
                with patch("service.searchService.rrf_fuse", wraps=rrf_fuse) as fuse:
                    # 执行实际的 RRF 预排序
                    final_ids = await service.pre_ranking(request)
                # 取出四路排名输入
                ranked_lists = fuse.call_args.kwargs["ranked_lists"]
                # 取出 RRF 的 k 参数
                k = fuse.call_args.kwargs["k"]
                # 取出四路排名输入
                report_case(case, ranked_lists, final_ids, k, top_n, totals)
                if rerank:
                    # 和搜索服务一样，精排使用按 RRF 顺序取回的记忆。
                    memories = await memory_repo.search_memory(final_ids)
                    before_ids = [memory.id for memory in memories]
                    start = perf_counter()
                    try:
                        async with asyncio.timeout(30):
                            reranked = await service.fine_ranking(request, memories)
                    except (APIError, TimeoutError) as exc:
                        failed += 1
                        print(f"  精排失败（{type(exc).__name__}），本题保留召回统计")
                        continue
                    if memories:
                        durations.append(perf_counter() - start)
                    after_ids = [memory.id for memory in reranked]
                    relevant = case["relevant"]
                    comparisons.append((
                        ranking_scores(before_ids, relevant),
                        ranking_scores(after_ids, relevant),
                    ))
                    before_ranks, after_ranks = ranks(before_ids), ranks(after_ids)
                    print("  标注名次（RRF → 精排）")
                    for memory_id, memory_type in relevant.items():
                        print(f"    {memory_type} {memory_id} "
                              f"{before_ranks.get(memory_id, '-')} → {after_ranks.get(memory_id, '-')}")
    finally:
        await engine.dispose()
    report_summary(totals, top_n)
    if rerank:
        report_rerank_summary(comparisons, durations, failed)
        if not comparisons:
            raise ValueError("没有可用于精排对比的题目")


# 定义命令行程序入口
def main():
    # 配置命令行参数
    parser = argparse.ArgumentParser(description="评测 MiniMemo 的召回、RRF 粗排和精排")
    # 配置命令行参数
    parser.add_argument("--demo", action="store_true", help="使用样例名次，离线展示如何算指标")
    parser.add_argument("--rerank", action="store_true", help="用真实精排模型对比同一批 RRF 候选")
    # 配置命令行参数
    parser.add_argument("--cases", type=Path, help="标注题集的 JSON 文件")
    # 配置命令行参数
    parser.add_argument("--user-id")
    # 配置命令行参数
    parser.add_argument("--agent-id", help="数据库中的内部 Agent ID")
    # 配置命令行参数
    args = parser.parse_args()
    if args.demo and args.rerank:
        parser.error("--rerank 需要真实候选正文，请使用真实评测")
    if not args.demo and not (args.cases and args.user_id and args.agent_id):
        # 配置命令行参数
        parser.error("真实评测需要 --cases、--user-id 和 --agent-id")
    try:
        # 读取并解析题集文件
        cases = load_cases(args.cases or EXAMPLE_CASES)
        if args.demo:
            run_demo(cases)
        else:
            # 运行异步真实评测
            loop_factory = asyncio.SelectorEventLoop if sys.platform == "win32" else None
            with asyncio.Runner(loop_factory=loop_factory) as runner:
                runner.run(run_live(cases, args.user_id, args.agent_id, rerank=args.rerank))
    except (OSError, ValueError) as exc:
        # 配置命令行参数
        parser.exit(1, f"评测失败：{exc}\n")


# 直接运行文件时才调用主函数
if __name__ == "__main__":
    main()
