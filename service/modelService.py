import time
from functools import lru_cache

from config.data import settings
from config.modelConfig import modelConfig
from openai import OpenAI
from loguru import logger
from prompt.makeMemoryPrompt import MEMORY_PROMPT
from tools.processJSON import json_to_dict


class modelService:





    @staticmethod
    def chat(origin_content:str,model:modelConfig,additional_kwargs:dict|None=None) -> list:
        client=modelService.get_client(api_key=model.api_key,base_url=model.base_url)
        prompt=MEMORY_PROMPT+"\n"+origin_content
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
                if i==settings.MAX_RETRY_TIMES-1:
                    logger.error(f"记忆格式化失败，错误信息：{e}")
                    raise e
                time.sleep(2 ** i)
        raise RuntimeError("记忆格式化失败")






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

















if __name__ == "__main__":
    model_service = modelService()
    model_service.chat(
        "这是一个测试内容",
        modelConfig(
        model_name="DeepSeek",
        base_url="https://api.chat.csu.edu.cn/v1",
        api_key="sk-JsCtaPDtaGo8eSkgJRcyMETFgWc1yRYmdK0fGCrxJZ7uJpfy"
    ))
