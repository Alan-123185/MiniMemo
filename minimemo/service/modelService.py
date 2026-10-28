import json
import re
import time
from functools import lru_cache
from minimemo.common.existFact import existFact
from  minimemo.config.data import settings
from  minimemo.config.modelConfig import modelConfig
from openai import OpenAI
from loguru import logger
from minimemo.prompt.memoryPrompt.episodeMemoryPrompt import EPISODE_MEMORY_PROMPT
from minimemo.prompt.queryChangePrompt import QUERY_CHANGE_PROMPT
from  minimemo.prompt.similarityJudgePrompt import similarity_judge_prompt
from  minimemo.tools.processJSON import json_to_dict


class modelService:



    @staticmethod
    def to_memory(origin_content:str,model:modelConfig,additional_kwargs:dict|None=None) -> list:
        client=modelService.get_client(api_key=model.api_key,base_url=model.base_url)
        prompt=EPISODE_MEMORY_PROMPT+"\n"+origin_content
        if additional_kwargs:
            prompt+= "\n此外，用户还输入了少量附加信息:"
            for key, value in additional_kwargs.items():
                prompt += f"\n{key}: {value}"

        for i in range(settings.MAX_RETRY_TIMES):
            try:
                res=client.chat.completions.create(
                    model=model.model_name,
                    messages=[{"role": "user", "content":prompt}],
                )
                output = json_to_dict(res.choices[0].message.content)
                return output["memories"]
            except Exception as e:
                logger.info(f"记忆格式化失败({i+1}/{settings.MAX_RETRY_TIMES})")
                logger.info(f"对话排序失败，错误信息：{e}")
                if i==settings.MAX_RETRY_TIMES-1:
                    logger.error(f"记忆格式化失败，错误信息：{e}")
                    raise e
                time.sleep(2 ** i)
        raise RuntimeError("记忆格式化失败")



    @staticmethod
    def judge_similarity(fact1:str,fact2:list[existFact],model:modelConfig) -> dict:
        client=modelService.get_client(api_key=model.api_key,base_url=model.base_url)
        prompt=similarity_judge_prompt.format(fact=fact1,existing_memories=[f"[ID: {fact.memory_id}] {fact.content}" for fact in fact2])
        for i in range(settings.MAX_RETRY_TIMES):
            try:
                res=client.chat.completions.create(
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
                time.sleep(2 ** i)
        raise RuntimeError("记忆相似度判断失败")



    """
    将最近几轮对话内容校准
    query 改写
    """
    @staticmethod
    def sort_question(query:list[str],model:modelConfig) -> list[str]:
        client=modelService.get_client(api_key=model.api_key,base_url=model.base_url)
        prompt=QUERY_CHANGE_PROMPT.format(history_text="\n".join(query))
        for i in range(settings.MAX_RETRY_TIMES):
            try:
                res=client.chat.completions.create(
                    model=model.model_name,
                    messages=[{"role": "user", "content":prompt}],
                )
                output = res.choices[0].message.content
                output = re.sub(r'```json\s*|\s*```', '', output).strip()
                ret=json.loads(output)
                if isinstance(ret,list) and all(isinstance(item,str) for item in ret):
                    return ret
            except Exception as e:
                logger.info(f"对话排序失败({i+1}/{settings.MAX_RETRY_TIMES})")
                logger.info(f"对话排序失败，错误信息：{e}")
                if i==settings.MAX_RETRY_TIMES-1:
                    logger.error(f"对话排序失败，错误信息：{e}")
                    raise e
                time.sleep(2 ** i)
        raise RuntimeError("对话排序失败")



    @staticmethod
    def embedding(fact:str,model:modelConfig) -> list[float]:
        client=modelService.get_client(api_key=model.api_key,base_url=model.base_url)
        for i in range(settings.MAX_RETRY_TIMES):
            try:
                res=client.embeddings.create(
                    model=model.model_name,
                    input=fact
                )
                return res.data[0].embedding
            except Exception as e:
                logger.info(f"记忆向量化失败({i+1}/{settings.MAX_RETRY_TIMES})")
                if i==settings.MAX_RETRY_TIMES-1:
                    logger.error(f"记忆向量化失败，错误信息：{e}")
                    raise e
                time.sleep(2 ** i)
        raise RuntimeError("记忆向量化失败")






    @staticmethod
    @lru_cache(maxsize=8)
    def get_client(api_key: str, base_url: str) -> OpenAI:
        return OpenAI(api_key=api_key, base_url=base_url)





