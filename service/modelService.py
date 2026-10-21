from config.modelConfig import get_pool, modelConfig
from openai import OpenAI

from prompt.makeMemoryPrompt import MEMORY_PROMPT


class modelService:

    def process_original_content(self):
        # Implement the logic to process the model
        model=get_pool()
        chat_model=model.chat
        embedding_model=model.embedding












    def _chat(self,model:modelConfig):
        client=OpenAI(
            api_key=model.api_key,
            base_url=model.base_url
        )
        prompt=MEMORY_PROMPT
        res=client.chat.completions.create(
            model=model.model_name,
            messages=[{"role": "user", "content": prompt}]
        )
        output=res.choices[0].message.content























if __name__ == "__main__":
    model_service = modelService()
    model_service.chat(modelConfig(
        model_name="DeepSeek",
        base_url="https://api.chat.csu.edu.cn/v1",
        api_key="sk-JsCtaPDtaGo8eSkgJRcyMETFgWc1yRYmdK0fGCrxJZ7uJpfy"
    ))
