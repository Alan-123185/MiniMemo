import os
from typing import Literal
import httpx
from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import ValidationError
from common.memoryInfo import returnMemoryInfo
from common.requestSchema.searchRequest import searchRequest
from common.requestSchema.storeRequest import originContentStoreRequest
from common.result import Result


async def _post_memory(base_url: str, action: str, payload: dict) -> Result:
    try:
        async with httpx.AsyncClient(
            base_url=base_url, timeout=httpx.Timeout(120, connect=5), trust_env=False
        ) as client:
            response = await client.post(f"/MiniMemo/memory/{action}", json=payload)
    except httpx.TimeoutException as exc:
        raise ToolError("MiniMemo 请求超时，处理结果未知") from exc
    except httpx.RequestError as exc:
        raise ToolError("无法连接 MiniMemo API，请检查服务是否已启动") from exc

    try:
        result = Result.model_validate_json(response.content)
    except ValidationError as exc:
        raise ToolError(f"MiniMemo 返回了无效响应（HTTP {response.status_code}）") from exc
    if "code" not in result.model_fields_set:
        raise ToolError(f"MiniMemo 返回了无效响应（HTTP {response.status_code}）")
    if not response.is_success or result.code != 200:
        message = result.message or result.error or "请求失败"
        raise ToolError(f"MiniMemo：{message}（HTTP {response.status_code}）")
    return result



def build_server(base_url: str, user_id: str, agent_name: str) -> MCPServer:
    server = MCPServer("MiniMemo")

    @server.tool()
    async def add_memory(
        content: str,
        session_id: str = "default",
        role: Literal["user", "assistant", "system"] = "system",
    ) -> dict[str, bool]:
        """
        这个工具用于保存未来会话可能用到的信息。用户要求记住某件事，或对话中确认了长期偏好、
        项目背景、决定或约定时调用。content 应写成脱离当前对话也能读懂的一条信息，
        保留主体和必要条件。临时进度和未经确认的推测通常跳过。
        session_id 指定来源会话，role 标记信息来源；两者可省略。
        """
        request = originContentStoreRequest(
            user_id=user_id,
            agent_id=agent_name,
            origin_content=content,
            session_id=session_id,
            role=role,
        )
        await _post_memory(base_url, "add", request.model_dump(mode="json"))
        return {"saved": True}



    @server.tool()
    async def search_memory(query: str) -> list[returnMemoryInfo]:
        """
        检索已有记忆。
        使用场景：用户提到以前的讨论、偏好、项目决定或约定，或者当前任务依赖历史背景时，先用这个工具回查。
        :param query: 用自然语言描述填一个具体问题或者你希望检索的内容或者记忆
        :return: 返回匹配的内容、记忆类型和更新时间；空列表表示本次没有找到匹配项。

        """
        request = searchRequest(user_id=user_id, agent_id=agent_name, query=query)
        result = await _post_memory(base_url, "search", request.model_dump(mode="json"))
        if not isinstance(result.response, list):
            raise ToolError("MiniMemo 未返回记忆列表")
        try:
            return [returnMemoryInfo.model_validate(memory) for memory in result.response]
        except ValidationError as exc:
            raise ToolError("MiniMemo 返回的记忆格式无效") from exc

    return server


if __name__ == "__main__":
    config_names = ("MINIMEMO_USER_ID", "MINIMEMO_AGENT_NAME")
    missing = [name for name in config_names if not os.getenv(name, "").strip()]
    if missing:
        raise SystemExit(f"请设置 MCP 环境变量：{', '.join(missing)}")
    build_server(
        os.getenv("MINIMEMO_API_URL", "http://127.0.0.1:1314"),
        user_id=os.environ["MINIMEMO_USER_ID"],
        agent_name=os.environ["MINIMEMO_AGENT_NAME"]
    ).run(transport="stdio")
