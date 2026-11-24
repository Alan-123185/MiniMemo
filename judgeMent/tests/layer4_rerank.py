"""第 4 层：四路召回 + RRF 融合 + 精排重排序。

在项目根目录运行：
    python -m judgeMent.tests.layer4_rerank --user-id USER --agent-id AGENT

在层 3 的候选上再走一遍精排，除统计最终排序外，还给出 RRF 与精排的逐题对比和耗时。
"""

from judgeMent.tests import recall_common as common

LAYER = "layer4_rerank"
NAME = "层4·四路+RRF+精排"


def main():
    parser = common.build_parser(__doc__)
    args = parser.parse_args()
    common.setup_log(LAYER, NAME)
    cases = common.load_cases(args.cases)
    try:
        common.run(lambda: common.run_single(
            cases, args.user_id, args.agent_id, rerank=True,
        ))
    except (OSError, ValueError) as exc:
        parser.exit(1, f"评测失败：{exc}\n")


if __name__ == "__main__":
    main()
