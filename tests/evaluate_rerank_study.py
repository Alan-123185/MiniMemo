"""比较全量与 top25，扫描精排窗口，并做标注分组的两折验证。"""

import argparse
import asyncio
import sys
from collections import Counter
from math import ceil
from pathlib import Path
from statistics import median
from time import perf_counter
from unittest.mock import patch

from sqlalchemy import select

from common.requestSchema.searchRequest import searchRequest
from config.data import settings
from db.session import create_session, engine
from models.agent import Agent
from models.memoryModel.memory import Memory
from repository.embeddingRepository import embeddingRepository
from repository.memoryRepository import memoryRepository
from repository.userRepository import userRepository
from service.searchService import searchService
from tests.evaluate_recall import load_cases, ranking_scores

LIMITS = range(15, 41)
CONTROL = 25


def split_cases(cases):
    # 共享任一标注 ID 的题归到同一组，再按题数和标注数配平两半。
    groups = []
    for index, case in enumerate(cases):
        labels = set(case["relevant"])
        indices = [index]
        connected = [group for group in groups if labels & group[0]]
        for group_labels, group_indices in connected:
            groups.remove((group_labels, group_indices))
            labels.update(group_labels)
            indices.extend(group_indices)
        groups.append((labels, indices))

    half = len(cases) // 2
    subsets = {(0, 0): ()}
    for _, indices in groups:
        labels = sum(len(cases[index]["relevant"]) for index in indices)
        for (size, total), subset in list(subsets.items()):
            if size + len(indices) <= half:
                subsets.setdefault((size + len(indices), total + labels), subset + tuple(indices))
    all_labels = sum(len(case["relevant"]) for case in cases)
    balanced = [key for key in subsets if key[0] == half]
    if not balanced or len(cases) % 2:
        raise ValueError("当前题集无法按共享标注 ID 切为等大的两半")
    best = min(balanced, key=lambda key: (abs(all_labels - 2 * key[1]), subsets[key]))
    a = sorted(subsets[best])
    b = sorted(set(range(len(cases))) - set(a))
    return a, b


def measure(records, order_for):
    totals = Counter()
    for record in records:
        relevant = record["relevant"]
        order = order_for(record)
        totals.update(ranking_scores(order, relevant))
        totals["retained"] += len(set(order) & relevant.keys())
    totals["ndcg5"] /= len(records)
    return totals


def score_deltas(records, before, after):
    deltas = []
    for r in records:
        relevant = r["relevant"]
        a = ranking_scores(before(r), relevant)["ndcg5"]
        b = ranking_scores(after(r), relevant)["ndcg5"]
        deltas.append(round(b - a, 12))
    up = sum(delta > 0 for delta in deltas)
    down = sum(delta < 0 for delta in deltas)
    return sum(deltas) / len(deltas), up, len(deltas) - up - down, down


def replay(record, limit):
    allowed = set(record["rrf"][:limit])
    return [memory_id for memory_id in record["full"] if memory_id in allowed]


def print_scores(label, totals, records):
    cases = len(records)
    marks = sum(len(record["relevant"]) for record in records)
    print(f"{label:<16} {totals['retained']:>3}/{marks:<3}   {totals['hit1']:>2}/{cases:<2} "
          f" {totals['hit5']:>2}/{cases:<2} {totals['evidence5']:>5} "
          f"{totals['evidence10']:>6} {totals['ndcg5']:>8.4f}", flush=True)


def print_deltas(label, records, before, after):
    delta, up, tie, down = score_deltas(records, before, after)
    print(f"{label}  ΔnDCG@5 {delta:+.4f}，上升 {up}，持平 {tie}，下降 {down}")


async def timed_rerank(service, request, memories):
    start = perf_counter()
    async with asyncio.timeout(30):
        ranked = await service.fine_ranking(request, memories)
    return [memory.id for memory in ranked], perf_counter() - start


async def validate_cases(session, cases, user_id, agent_id):
    agent = await session.get(Agent, agent_id)
    if agent is None or agent.user_id != user_id:
        raise ValueError("找不到该用户下的 Agent，请使用内部 agent_id")
    expected = {memory_id: kind for case in cases for memory_id, kind in case["relevant"].items()}
    rows = await session.execute(
        select(Memory.id, Memory.memory_type).where(
            Memory.id.in_(expected), Memory.agent_id == agent_id, Memory.is_delete.is_(False),
        )
    )
    if dict(rows.all()) != expected:
        raise ValueError("有标注不存在、已删除、不属于该 Agent 或类型不符")


def save_chart(path, scores, case_count):
    from matplotlib import pyplot as plt

    limits = list(scores)
    hits = [scores[n]["hit5"] for n in limits]
    fig, (quality, hit) = plt.subplots(2, 1, sharex=True, figsize=(8, 5))
    quality.plot(limits, [scores[n]["ndcg5"] for n in limits], marker=".", color="#176b65")
    hit.plot(limits, hits, marker=".", color="#93552a")
    for axis in (quality, hit):
        axis.axvline(CONTROL, color="#7f8790", linestyle="--", linewidth=1)
        axis.grid(alpha=0.25)
    quality.set(title=f"MiniMemo candidate window sweep · {case_count} queries · replay", ylabel="nDCG@5")
    hit.set(xlabel="RRF_TOP_N", ylabel="Hit@5 (queries)",
            ylim=(max(0, min(hits) - 1.5), case_count + 0.25))
    hit.yaxis.get_major_locator().set_params(integer=True)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


async def run_study(cases, user_id, agent_id, chart=None):
    a, b = split_cases(cases)
    full_limit = settings.BM25_CANDIDATE_LIMIT + sum((
        settings.RECALL_CANDIDATE_LIMIT_ORIGIN,
        settings.RECALL_CANDIDATE_LIMIT_EPISODIC,
        settings.RECALL_CANDIDATE_LIMIT_SEMANTIC,
    ))
    records = []
    try:
        async with create_session() as session:
            await validate_cases(session, cases, user_id, agent_id)
            repo = memoryRepository(session)
            service = searchService(embeddingRepository(session), repo, userRepository(session))
            for index, case in enumerate(cases, 1):
                request = searchRequest(query=case["query"], user_id=user_id, agent_id=agent_id)
                with patch.object(settings, "RRF_TOP_N", full_limit):
                    memory_ids = await service.pre_ranking(request)
                memories = await repo.search_memory(memory_ids)
                record = {"relevant": case["relevant"], "rrf": [m.id for m in memories]}
                # 按题交替请求顺序，让两种窗口都覆盖先发和后发。
                order = ("full", "top25") if index % 2 else ("top25", "full")
                for variant in order:
                    batch = memories if variant == "full" else memories[:CONTROL]
                    record[variant], record[f"{variant}_seconds"] = await timed_rerank(service, request, batch)
                records.append(record)
                print(f"第 {index}/{len(cases)} 题  候选 {len(memories)} → {len(memories[:CONTROL])}  "
                      f"全量 {record['full_seconds']:.2f}s / top25 {record['top25_seconds']:.2f}s", flush=True)

            heading = "阶段              保留标注     Hit@1  Hit@5  证据@5 证据@10  nDCG@5"
            full_rrf = lambda r: r["rrf"]
            short_rrf = lambda r: r["rrf"][:CONTROL]
            short_rerank = lambda r: r["top25"]
            full_rerank = lambda r: r["full"]
            print(f"\n{heading}")
            for name, order_for in (
                ("全量 RRF", full_rrf), ("top25 RRF", short_rrf),
                ("top25 精排", short_rerank), ("全量精排", full_rerank),
            ):
                print_scores(name, measure(records, order_for), records)
            print_deltas("只截断", records, full_rrf, short_rrf)
            print_deltas("top25 上精排", records, short_rrf, short_rerank)
            print_deltas("两种精排窗口", records, full_rerank, short_rerank)
            for name in ("full", "top25"):
                times = sorted(r[f"{name}_seconds"] for r in records)
                print(f"{name} 精排耗时 P50={median(times):.2f}s P95={times[ceil(.95 * len(times)) - 1]:.2f}s")
            savings = [r["full_seconds"] - r["top25_seconds"] for r in records]
            print(f"同题耗时减少的中位数 {median(savings):+.2f}s，top25 更快 {sum(x > 0 for x in savings)}/{len(records)} 题")

            scores = {n: measure(records, lambda r: replay(r, n)) for n in LIMITS}
            print("\n候选窗口扫描（使用全量精排顺序回放）")
            for n, totals in scores.items():
                print(f"N={n:>2}  Hit@5={totals['hit5']}/{len(records)}  nDCG@5={totals['ndcg5']:.4f}")
            replay_matches = sum(replay(r, CONTROL)[:5] == r["top25"][:5] for r in records)
            print(f"top25 回放与实跑前 5 完全同序 {replay_matches}/{len(records)} 题", flush=True)
            if chart is not None:
                save_chart(chart, scores, len(records))

            for name, train_indices, held_indices in (("A → B", a, b), ("B → A", b, a)):
                train = [records[i] for i in train_indices]
                held = [records[i] for i in held_indices]
                train_scores = {n: measure(train, lambda r: replay(r, n))["ndcg5"] for n in LIMITS}
                selected = max(LIMITS, key=lambda n: (round(train_scores[n], 12), -n))
                print(f"\n{name}  选点题号 {[i + 1 for i in train_indices]}", flush=True)
                print(f"训练选 N={selected}，nDCG@5={train_scores[selected]:.4f}，固定 25 回放={train_scores[CONTROL]:.4f}", flush=True)
                if selected != CONTROL:
                    for index, record in zip(held_indices, held):
                        request = searchRequest(query=cases[index]["query"], user_id=user_id, agent_id=agent_id)
                        memories = await repo.search_memory(record["rrf"][:selected])
                        record["selected"], _ = await timed_rerank(service, request, memories)
                        print(f"验证 N={selected}  第 {index + 1} 题完成", flush=True)
                print(heading)
                print_scores("全量精排", measure(held, full_rerank), held)
                print_scores("固定 25 精排", measure(held, short_rerank), held)
                if selected != CONTROL:
                    print_scores(f"选定 {selected} 精排", measure(held, lambda r: r["selected"]), held)
                print_deltas("验证集固定 25 vs 全量", held, full_rerank, short_rerank)
    finally:
        await engine.dispose()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--user-id", required=True)
    parser.add_argument("--agent-id", required=True, help="数据库中的内部 Agent ID")
    parser.add_argument("--chart", type=Path, help="可选的曲线 PNG 输出路径")
    args = parser.parse_args()
    cases = load_cases(args.cases)
    loop = asyncio.SelectorEventLoop if sys.platform == "win32" else None
    with asyncio.Runner(loop_factory=loop) as runner:
        runner.run(run_study(cases, args.user_id, args.agent_id, args.chart))


if __name__ == "__main__":
    main()
