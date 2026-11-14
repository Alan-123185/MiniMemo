from typing import Literal

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from common.exceptions import BusinessException, ConflictException, NotFoundException
from config.modelConfig import UserModelConfig
from models.agent import Agent
from models.user import User

"""
11.14
这个类是Codex写的 风格和之前的大相径庭 先不管 到时候再搞
"""
class userRepository:
    def __init__(self, session: AsyncSession):
        self.session = session




    async def register_user(self, user_id: str, config: UserModelConfig | None = None) -> None:
        """注册用户，并在同一事务中保存选填的模型配置。"""
        configs = {}
        if config is not None:
            configs = config.model_dump(mode="json", exclude_none=True)
        statement = (
            insert(User)
            .values(user_id=user_id, **configs)
            .on_conflict_do_nothing(index_elements=[User.user_id])
            .returning(User.user_id)
        )
        if await self.session.scalar(statement) is None:
            raise ConflictException("用户已存在")
        await self.session.commit()




    async def get_models(self, user_id: str) -> UserModelConfig:
        """读取用户保存的两项模型配置，未配置的项为 None。"""
        user = await self.session.get(User, user_id)
        if user is None:
            raise NotFoundException("用户不存在")
        return UserModelConfig.model_validate({"embedding": user.embedding, "chat": user.chat})




    async def get_models_by_agent(self, agent_id: str) -> UserModelConfig:
        """按内部 Agent ID 查询其所属用户的模型配置。"""
        user_id = await self.session.scalar(select(Agent.user_id).where(Agent.id == agent_id))
        if user_id is None:
            raise NotFoundException("Agent 不存在")
        return await self.get_models(user_id)


    async def add_models(self, user_id: str, config: UserModelConfig) -> None:
        """添加尚未设置的配置，两项一起添加时全部校验后提交。"""
        configs = config.model_dump(mode="json", exclude_none=True)
        if not configs:
            raise BusinessException("请至少提供一项模型配置")

        # FOR NO KEY UPDATE 将同一用户的配置写入串行化，兼容 Agent 外键检查。
        user = await self.session.get(User, user_id, with_for_update={"key_share": True})
        if user is None:
            raise NotFoundException("用户不存在")
        for kind in configs:
            if getattr(user, kind) is not None:
                raise ConflictException(f"{kind} 模型已配置")

        for kind, value in configs.items():
            setattr(user, kind, value)
        await self.session.commit()




    async def update_models(self, user_id: str, config: UserModelConfig) -> None:
        """替换请求中指定的已有配置，两项一起更新时全部校验后提交。"""
        configs = config.model_dump(mode="json", exclude_none=True)
        if not configs:
            raise BusinessException("请至少提供一项模型配置")

        user = await self.session.get(User, user_id, with_for_update={"key_share": True})
        if user is None:
            raise NotFoundException("用户不存在")
        for kind in configs:
            if getattr(user, kind) is None:
                raise NotFoundException(f"{kind} 模型尚未配置")

        for kind, value in configs.items():
            setattr(user, kind, value)
        await self.session.commit()




    async def delete_model(self, user_id: str, kind: Literal["embedding", "chat"]) -> None:
        """清空指定的一项模型配置。"""
        if kind not in ("embedding", "chat"):
            raise BusinessException("模型类型必须是 embedding 或 chat")
        user = await self.session.get(User, user_id, with_for_update={"key_share": True})
        if user is None:
            raise NotFoundException("用户不存在")
        if getattr(user, kind) is None:
            raise NotFoundException(f"{kind} 模型尚未配置")
        setattr(user, kind, None)
        await self.session.commit()
