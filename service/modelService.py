import asyncio
from functools import lru_cache
from common.existFact import existFact
from  config.data import settings
from  config.modelConfig import modelConfig
from openai import AsyncOpenAI
from loguru import logger
from prompt.memoryPrompt.episodeMemoryPrompt import EPISODE_MEMORY_PROMPT
from prompt.memoryPrompt.semanticMemoryPrompt import SEMANTIC_MEMORY_PROMPT
from prompt.queryChangePrompt import QUERY_CHANGE_PROMPT
from  prompt.similarityJudgePrompt import similarity_judge_prompt
from  tools.processJSON import json_to_dict


class modelService:



    @staticmethod
    async def to_episodic_memory(origin_content:str,model:modelConfig) -> tuple[list, int]:
        client=modelService.get_async_client(api_key=model.api_key,base_url=model.base_url)
        prompt=EPISODE_MEMORY_PROMPT+"\n"+origin_content
        for i in range(settings.MAX_RETRY_TIMES):
            try:
                res=await client.chat.completions.create(
                    model=model.model_name,
                    messages=[{"role": "user", "content":prompt}],
                )
                output = json_to_dict(res.choices[0].message.content)
                memories=output["memories"]
                #truncate_from：结尾是否把一件事讲到一半，-1 表示完整，否则是截断开始的原文编号
                return memories, int(output.get("truncate_from", -1))
            except Exception as e:
                logger.info(f"记忆格式化失败({i+1}/{settings.MAX_RETRY_TIMES})")
                logger.info(f"对话排序失败，错误信息：{e}")
                if i==settings.MAX_RETRY_TIMES-1:
                    logger.error(f"记忆格式化失败，错误信息：{e}")
                    raise e
                await asyncio.sleep(2 ** i)
        raise RuntimeError("记忆格式化失败")



    @staticmethod
    async def to_semantic_memory(episodic_memories:str,model:modelConfig) -> list:
        client=modelService.get_async_client(api_key=model.api_key,base_url=model.base_url)
        prompt=SEMANTIC_MEMORY_PROMPT+"\n"+episodic_memories
        for i in range(settings.MAX_RETRY_TIMES):
            try:
                res=await client.chat.completions.create(
                    model=model.model_name,
                    messages=[{"role": "user", "content":prompt}],
                )
                output = json_to_dict(res.choices[0].message.content)
                return output["memories"]
            except Exception as e:
                logger.info(f"语义记忆提炼失败({i+1}/{settings.MAX_RETRY_TIMES})")
                logger.info(f"语义记忆提炼失败，错误信息：{e}")
                if i==settings.MAX_RETRY_TIMES-1:
                    logger.error(f"语义记忆提炼失败，错误信息：{e}")
                    raise e
                await asyncio.sleep(2 ** i)
        raise RuntimeError("语义记忆提炼失败")



    @staticmethod
    async def judge_similarity(fact1:str,fact2:list[existFact],model:modelConfig) -> dict:
        client=modelService.get_async_client(api_key=model.api_key,base_url=model.base_url)
        prompt=similarity_judge_prompt.format(fact=fact1,existing_memories=[f"[ID: {fact.memory_id}] {fact.content}" for fact in fact2])
        for i in range(settings.MAX_RETRY_TIMES):
            try:
                res=await client.chat.completions.create(
                    model=model.model_name,
                    messages=[{"role": "user", "content":prompt}],
                )
                output =  json_to_dict(res.choices[0].message.content)
                logger.info(f"记忆相似度判断：{output}")
                return output
            except Exception as e:
                logger.info(f"记忆相似度判断失败({i+1}/{settings.MAX_RETRY_TIMES})")
                logger.info(f"对话排序失败，错误信息：{e}")
                if i==settings.MAX_RETRY_TIMES-1:
                    logger.error(f"记忆相似度判断失败，错误信息：{e}")
                    raise e
                await asyncio.sleep(2 ** i)
        raise RuntimeError("记忆相似度判断失败")



    """
    将最近几轮对话内容校准
    query 改写
    11.14
    决定由外接agent自主传入检索内容 不需要进行query改写
    """
    # @staticmethod
    # async def sort_question(query:list[str],model:modelConfig) -> list[str]:
    #     client=modelService.get_async_client(api_key=model.api_key,base_url=model.base_url)
    #     prompt=QUERY_CHANGE_PROMPT.format(history_text="\n".join(query))
    #     for i in range(settings.MAX_RETRY_TIMES):
    #         try:
    #             res=await client.chat.completions.create(
    #                 model=model.model_name,
    #                 messages=[{"role": "user", "content":prompt}],
    #             )
    #             output = res.choices[0].message.content
    #             output = re.sub(r'```json\s*|\s*```', '', output).strip()
    #             ret=json.loads(output)
    #             if isinstance(ret,list) and all(isinstance(item,str) for item in ret):
    #                 return ret
    #         except Exception as e:
    #             logger.info(f"对话排序失败({i+1}/{settings.MAX_RETRY_TIMES})")
    #             logger.info(f"对话排序失败，错误信息：{e}")
    #             if i==settings.MAX_RETRY_TIMES-1:
    #                 logger.error(f"对话排序失败，错误信息：{e}")
    #                 raise e
    #             await asyncio.sleep(2 ** i)
    #     raise RuntimeError("对话排序失败")



    @staticmethod
    async def embedding(fact:str,model:modelConfig) -> list[float]:
        client=modelService.get_async_client(api_key=model.api_key,base_url=model.base_url)
        for i in range(settings.MAX_RETRY_TIMES):
            try:
                res=await client.embeddings.create(
                    model=model.model_name,
                    input=fact
                )
                return res.data[0].embedding
            except Exception as e:
                logger.info(f"记忆向量化失败({i+1}/{settings.MAX_RETRY_TIMES})")
                if i==settings.MAX_RETRY_TIMES-1:
                    logger.error(f"记忆向量化失败，错误信息：{e}")
                    raise e
                await asyncio.sleep(2 ** i)
        raise RuntimeError("记忆向量化失败")






    @staticmethod
    @lru_cache(maxsize=8)
    def get_async_client(api_key: str, base_url: str) -> AsyncOpenAI:
        return AsyncOpenAI(api_key=api_key, base_url=base_url)




