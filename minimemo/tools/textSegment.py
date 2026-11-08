import jieba

"""
中文分词
PG 的 simple 配置切不动中文，整句会被当成一个 token，
所以必须在应用层先切开，再把结果写进 content_seg 供 to_tsvector 建索引
"""


def segment(text: str) -> str:
    """
    把一段文本切成空格分隔的词串
    """
    return " ".join(jieba.cut(text))
