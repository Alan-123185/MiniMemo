from minimemo.models.memoryModel.memory import Memory
from minimemo.models.origin_content import originContent
from minimemo.repository.memoryRepository import memoryRepository


"""
原文仓库
原文也是记忆，继承结构与情景/语义一致，
所以增删改查全部复用基类，只有“新增”需要处理 additional_kwargs
"""


class originContentRepository(memoryRepository):
    kind = "origin_content"
    model = originContent

    def add_memory(
        self,
        memories: list[dict],
        agent_id: str,
        origin_content_id: str | None = None,
    ) -> None:
        """
        批量新增原文
        origin_content_id 对原文自身没有意义（它就是原文本体），签名保留只是为了和基类一致
        """
        for memory in memories:
            memo = originContent(
                content=memory["content"],
                agent_id=agent_id,
                additional_kwargs=memory.get("additional_kwargs"),
            )
            self._add_with_vector(memo, agent_id, memory)
        self.session.commit()

    def add_content(self, content: originContent, payload: dict | None = None) -> None:
        """
        单条新增的语法糖，传了 payload 才会挂向量，不传就只存内容

        id 是父表 memory 上的 Python 端默认值，要 flush 之后才会生成，
        所以这里直接复用基类的 _add_with_vector（内部会 flush），
        调完之后 content.id 就能读，调用方拿它回填 origin_content_id
        """
        if payload and payload.get("embedding"):
            self._add_with_vector(content, content.agent_id, payload)
        else:
            self.session.add(content)
        self.session.commit()

    def search_content(self, content_ids: list[str]) -> list[Memory]:
        """
        按 id 列表召回原文，返回顺序与传入顺序一致
        """
        return self.search_memory(content_ids)
