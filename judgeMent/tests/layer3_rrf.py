"""第 3 层：四路召回 + RRF 融合，不精排。

在项目根目录运行：
    python -m judgeMent.tests.layer3_rrf --user-id USER --agent-id AGENT

RRF 把四路合成一个排序，按排序口径统计：候选召回率、Recall@RRF_TOP_N、Hit@5。
"""

from judgeMent.tests import recall_common as common

LAYER = "layer3_rrf"
NAME = "层3·四路+RRF"


def main():
    parser = common.build_parser(__doc__)
    args = parser.parse_args()
    common.setup_log(LAYER, NAME)
    cases = common.load_cases(args.cases)
    try:
        common.run(lambda: common.run_single(
            cases, args.user_id, args.agent_id,
        ))
    except (OSError, ValueError) as exc:
        parser.exit(1, f"评测失败：{exc}\n")


if __name__ == "__main__":
    main()
