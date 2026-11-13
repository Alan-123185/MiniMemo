"""用户内 Agent 编号与接口解析测试，不连接 PostgreSQL、MQ 或模型服务。

运行：python -m unittest discover -s tests -v
"""
import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import UUID

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DatabaseSession
from sqlalchemy.pool import StaticPool

from db.session import get_session
from models import Agent, Base, Memory, Session, User, memoryVector
from repository.agentRepository import agentRepository
from router.agentRouter import router as agent_router
from router.consolidationRouter import router as consolidation_router
from router.memoryRouter import router as memory_router
from router.sessionRouter import router as session_router
from service.consolidationService import consolidationService
from service.dependencies import get_memory_service


class MemoryDatabaseSession:
    """将仓储的异步调用接到真实的同步 SQLite 内存事务，无额外驱动依赖。"""

    def __init__(self, session):
        self.session = session

    async def execute(self, statement):
        return self.session.execute(statement)

    def add(self, instance):
        self.session.add(instance)

    async def flush(self):
        self.session.flush()

    async def commit(self):
        self.session.commit()


class AgentIdentityTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )

        @event.listens_for(self.engine, "connect")
        def enable_foreign_keys(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")

        Base.metadata.create_all(
            self.engine, tables=[User.__table__, Agent.__table__, Session.__table__]
        )
        self.session = DatabaseSession(self.engine, expire_on_commit=False)
        self.session.add_all([User(user_id="user-a"), User(user_id="user-b"), User(user_id="user-c")])
        self.session.commit()
        self.adapter = MemoryDatabaseSession(self.session)
        self.repo = agentRepository(self.adapter)
        for user_id in ("user-a", "user-b"):
            asyncio.run(self.repo.register_agent("assistant", user_id))
        self.agent_a = asyncio.run(self.repo.get_agent("assistant", "user-a"))
        self.agent_b = asyncio.run(self.repo.get_agent("assistant", "user-b"))

        self.app = FastAPI()
        for router in (agent_router, session_router, memory_router, consolidation_router):
            self.app.include_router(router)

        async def get_test_session():
            yield self.adapter

        self.memory_service = SimpleNamespace(
            add_origin_content=AsyncMock(), search_memory=AsyncMock(return_value=[])
        )
        self.app.dependency_overrides[get_session] = get_test_session
        self.app.dependency_overrides[get_memory_service] = lambda: self.memory_service
        self.client = TestClient(self.app)

    def tearDown(self):
        self.client.close()
        self.session.close()
        self.engine.dispose()

    def test_same_external_id_has_distinct_internal_ids_and_default_sessions(self):
        self.assertEqual(self.agent_a.agent_name, self.agent_b.agent_name)
        self.assertNotEqual(self.agent_a.id, self.agent_b.id)
        UUID(self.agent_a.id)
        UUID(self.agent_b.id)
        defaults = self.session.scalars(select(Session).where(Session.session_id == "default")).all()
        self.assertEqual({s.agent_id for s in defaults}, {self.agent_a.id, self.agent_b.id})

    def test_registration_is_idempotent_within_user(self):
        response = self.client.post(
            "/MiniMemo/agent/register", params={"user_id": "user-a", "agent_name": "assistant"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(self.session.scalars(select(Agent)).all()), 2)
        self.assertEqual(len(self.session.scalars(select(Session)).all()), 2)

    def test_registration_api_generates_internal_id_and_keeps_default_session(self):
        response = self.client.post(
            "/MiniMemo/agent/register", params={"user_id": "user-c", "agent_name": "assistant"}
        )
        self.assertEqual(response.status_code, 200)
        agent = asyncio.run(self.repo.get_agent("assistant", "user-c"))
        self.assertNotIn(agent.id, (self.agent_a.id, self.agent_b.id, "assistant"))
        default = self.session.scalars(select(Session).where(Session.agent_id == agent.id)).one()
        self.assertEqual(default.session_id, "default")

    def test_database_rejects_duplicate_external_id_for_same_user(self):
        self.session.add(Agent(user_id="user-a", agent_name="assistant"))
        with self.assertRaises(IntegrityError):
            self.session.flush()
        self.session.rollback()

    def test_lists_are_scoped_and_background_scan_still_lists_all(self):
        asyncio.run(self.repo.register_agent("notes", "user-a"))
        response_a = self.client.get("/MiniMemo/agent/list", params={"user_id": "user-a"})
        response_b = self.client.get("/MiniMemo/agent/list", params={"user_id": "user-b"})
        self.assertEqual(set(response_a.json()["response"]), {"assistant", "notes"})
        self.assertEqual(response_b.json()["response"], ["assistant"])
        self.assertEqual(len(asyncio.run(self.repo.get_agents())), 3)

    def test_same_session_name_is_isolated_by_internal_agent_id(self):
        for user_id in ("user-a", "user-b"):
            response = self.client.post("/MiniMemo/session/register", params={
                "user_id": user_id, "agent_name": "assistant", "session_id": "chat"
            })
            self.assertEqual(response.status_code, 200)
        chats = self.session.scalars(select(Session).where(Session.session_id == "chat")).all()
        self.assertEqual({s.agent_id for s in chats}, {self.agent_a.id, self.agent_b.id})

    def test_memory_writes_forward_internal_id_and_preserve_other_fields(self):
        for user_id, agent in (("user-a", self.agent_a), ("user-b", self.agent_b)):
            response = self.client.post("/MiniMemo/memory/add", params={"user_id": user_id}, json={
                "agent_name": "assistant", "origin_content": "hello", "session_id": "chat", "role": "user"
            })
            self.assertEqual(response.status_code, 200)
            forwarded = self.memory_service.add_origin_content.await_args.args[0]
            self.assertEqual(forwarded.agent_name, agent.id)
            self.assertEqual((forwarded.origin_content, forwarded.session_id, forwarded.role),
                             ("hello", "chat", "user"))

    def test_search_forwards_each_users_internal_id(self):
        for user_id, agent in (("user-a", self.agent_a), ("user-b", self.agent_b)):
            self.memory_service.search_memory.return_value = [SimpleNamespace(id="memory", content=user_id)]
            response = self.client.post("/MiniMemo/memory/search", params={"user_id": user_id}, json={
                "agent_name": "assistant", "query": ["hello"]
            })
            self.assertEqual(response.status_code, 200)
            forwarded = self.memory_service.search_memory.await_args.args[0]
            self.assertEqual(forwarded.agent_name, agent.id)
            self.assertEqual(forwarded.query, ["hello"])
            self.assertEqual(response.json()["response"], [{"id": "memory", "content": user_id}])

    def test_unknown_pair_and_other_users_internal_id_do_not_reach_memory_service(self):
        for external_id in ("assistant", self.agent_b.id):
            response = self.client.post("/MiniMemo/memory/search", params={"user_id": "user-c"}, json={
                "agent_name": external_id, "query": ["hello"]
            })
            self.assertEqual(response.status_code, 404)
        response = self.client.post("/MiniMemo/memory/add", params={"user_id": "user-c"}, json={
            "agent_name": "assistant", "origin_content": "hello"
        })
        self.assertEqual(response.status_code, 404)
        self.memory_service.search_memory.assert_not_awaited()
        self.memory_service.add_origin_content.assert_not_awaited()

    def test_consolidation_routes_forward_internal_ids(self):
        with patch.object(consolidationService, "consolidate_episodics", new_callable=AsyncMock) as episodic, \
             patch.object(consolidationService, "consolidate_semantics", new_callable=AsyncMock) as semantic:
            for user_id, agent in (("user-a", self.agent_a), ("user-b", self.agent_b)):
                response = self.client.post(
                    "/MiniMemo/consolidation/add_episodic_memory/assistant/session/chat",
                    params={"user_id": user_id},
                )
                self.assertEqual(response.status_code, 200)
                episodic.assert_awaited_with(agent.id, "chat")
                response = self.client.post(
                    "/MiniMemo/consolidation/add_semantinc_memory/assistant", params={"user_id": user_id}
                )
                self.assertEqual(response.status_code, 200)
                semantic.assert_awaited_with(agent.id)
            episodic.reset_mock()
            semantic.reset_mock()
            response = self.client.post(
                "/MiniMemo/consolidation/add_episodic_memory/assistant/session/chat",
                params={"user_id": "user-c"},
            )
            self.assertEqual(response.status_code, 404)
            response = self.client.post(
                "/MiniMemo/consolidation/add_semantinc_memory/assistant", params={"user_id": "user-c"}
            )
            self.assertEqual(response.status_code, 404)
            episodic.assert_not_awaited()
            semantic.assert_not_awaited()

    def test_user_id_is_required_at_all_external_entries(self):
        requests = [
            ("GET", "/MiniMemo/agent/list", {}),
            ("POST", "/MiniMemo/agent/register", {"params": {"agent_name": "assistant"}}),
            ("POST", "/MiniMemo/session/register", {"params": {"agent_name": "assistant", "session_id": "chat"}}),
            ("POST", "/MiniMemo/memory/add", {"json": {"agent_name": "assistant", "origin_content": "hello"}}),
            ("POST", "/MiniMemo/memory/search", {"json": {"agent_name": "assistant", "query": ["hello"]}}),
            ("POST", "/MiniMemo/consolidation/add_semantinc_memory/assistant", {}),
            ("POST", "/MiniMemo/consolidation/add_episodic_memory/assistant/session/chat", {}),
        ]
        for method, path, kwargs in requests:
            with self.subTest(path=path):
                self.assertEqual(self.client.request(method, path, **kwargs).status_code, 422)

    def test_unknown_session_owner_is_rejected_before_insert(self):
        response = self.client.post("/MiniMemo/session/register", params={
            "user_id": "user-c", "agent_name": "assistant", "session_id": "chat"
        })
        self.assertEqual(response.status_code, 404)
        self.assertEqual(len(self.session.scalars(select(Session)).all()), 2)

    def test_legacy_primary_keys_and_existing_child_references_still_work(self):
        self.session.add(Agent(id="legacy-agent", user_id="user-a", agent_name="legacy-agent"))
        self.session.flush()
        self.session.add(Session(agent_id="legacy-agent", session_id="legacy-chat"))
        self.session.commit()
        response = self.client.post("/MiniMemo/memory/search", params={"user_id": "user-a"}, json={
            "agent_name": "legacy-agent", "query": ["hello"]
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.memory_service.search_memory.await_args.args[0].agent_name, "legacy-agent")
        for model in (Session, Memory, memoryVector):
            self.assertEqual(next(iter(model.__table__.c.agent_id.foreign_keys)).target_fullname, "agents.id")


if __name__ == "__main__":
    unittest.main()
