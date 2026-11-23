"""第 2 层：三路向量 + bm25 全文召回，不做 RRF、不精排。

在项目根目录运行：
    python -m judgeMent.tests.layer2_bm25 --user-id USER --agent-id AGENT

四路等级相同，互为并列，按集合口径统计：一条标注被任一路召回即算召回，被任一路
排进前 5 即算该题命中。
"""

from judgeMent.tests import recall_common as common

LAYER = "layer2_bm25"
NAME = "层2·三路向量+bm25"


def main():
    parser = common.build_parser(__doc__)
    args = parser.parse_args()
    common.setup_log(LAYER, NAME)
    cases = common.load_cases(args.cases)
    try:
        common.run(lambda: common.run_multi(
            cases, args.user_id, args.agent_id, common.ROUTES,
        ))
    except (OSError, ValueError) as exc:
        parser.exit(1, f"评测失败：{exc}\n")


if __name__ == "__main__":
    main()
