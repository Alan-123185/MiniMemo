"""第 1 层：只看三路向量召回，不看 bm25、不做 RRF、不精排。

在项目根目录运行：
    python -m judgeMent.tests.layer1_vector --user-id USER --agent-id AGENT

三路等级相同，互为并列，没有共同排序，按集合口径统计：一条标注被任一路召回即算
召回，被任一路排进前 5 即算该题命中。
"""

from judgeMent.tests import recall_common as common

LAYER = "layer1_vector"
NAME = "层1·三路向量"


def main():
    parser = common.build_parser(__doc__)
    args = parser.parse_args()
    common.setup_log(LAYER, NAME)
    cases = common.load_cases(args.cases)
    try:
        common.run(lambda: common.run_multi(
            cases, args.user_id, args.agent_id, common.VECTOR_ROUTES,
        ))
    except (OSError, ValueError) as exc:
        parser.exit(1, f"评测失败：{exc}\n")


if __name__ == "__main__":
    main()
