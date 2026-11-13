"""非检索写操作的 Agent 归属测试，使用独立的 SQLite 内存数据库。"""
import asyncio
import unittest
from unittest.mock import patch

from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session as DatabaseSession
from sqlalchemy.schema import CreateTable

from common.memoryInfo import episodicMemoryInfo, semanticMemoryInfo
from config.data import settings
from models import (
    Agent, Memory, User, episodeOriginLink, episodicMemory, memoryVector,
    originContent, semanticMemory,
)
from repository.episodicMemoryRepository import episodicMemoryRepository
from repository.originContentRepository import originContentRepository
from repository.semanticMemoryRepository import semanticMemoryRepository
from service.consolidationService import consolidationService


class WriteSession:
    """仅适配异步方法，SQL、约束和提交/回滚均由真实内存数据库执行。"""

    def __init__(self, session):
        self.session = session
        self.commits = 0

    async def execute(self, statement):
        return self.session.execute(statement)

    def add(self, instance):
        self.session.add(instance)

    async def get(self, model, key):
        return self.session.get(model, key)

    async def delete(self, instance):
        self.session.delete(instance)

    async def flush(self):
        self.session.flush()

    async def commit(self):
        self.session.commit()
        self.commits += 1

    async def close(self):
        self.session.close()


class MemoryOwnershipTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")

        @event.listens_for(self.engine, "connect")
        def enable_foreign_keys(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")

        # 写测试不需要 PostgreSQL 的全文/向量索引，只创建原模型的表和外键。
        with self.engine.begin() as connection:
            for model in (User, Agent, Memory, originContent, episodicMemory,
                          semanticMemory, memoryVector, episodeOriginLink):
                connection.execute(CreateTable(model.__table__))

        self.session = DatabaseSession(self.engine, expire_on_commit=False)
        self.session.add_all([User(user_id="user-a"), User(user_id="user-b")])
        self.session.flush()
        self.session.add_all([
            Agent(id="internal-a", user_id="user-a", agent_name="assistant"),
            Agent(id="internal-b", user_id="user-b", agent_name="assistant"),
            Agent(id="internal-a2", user_id="user-a", agent_name="notes"),
        ])
        self.session.flush()
        self.vector = [0.0] * settings.EMBEDDING_DIM
        self.changed_vector = [1.0] * settings.EMBEDDING_DIM
        for suffix in ("a", "b", "a2"):
            owner = "internal-" + suffix
            records = [
                originContent(id="origin-" + suffix, agent_id=owner, content="origin-" + suffix),
                episodicMemory(id="episode-" + suffix, agent_id=owner, content="episode-" + suffix),
                semanticMemory(id="semantic-" + suffix, agent_id=owner, content="semantic-" + suffix, type="fact"),
            ]
            self.session.add_all(records)
            self.session.flush()
            self.session.add_all([
                memoryVector(id="vector-" + record.id, memory_id=record.id,
                             agent_id=owner, embedding=self.vector, embedding_model="test")
                for record in records
            ])
        self.session.commit()
        self.adapter = WriteSession(self.session)
        self.semantic_repo = semanticMemoryRepository(self.adapter)
        self.episode_repo = episodicMemoryRepository(self.adapter)
        self.origin_repo = originContentRepository(self.adapter)

    def tearDown(self):
        self.session.close()
        self.engine.dispose()

    def semantic_info(self):
        return semanticMemoryInfo(content="new fact", embedding=self.changed_vector, embedding_model="test")

    def episode_info(self):
        return episodicMemoryInfo(content="new episode", embedding=self.changed_vector,
                                  embedding_model="test", origin_content_id=["0"])

    def record(self, model, key):
        self.session.expire_all()
        return self.session.get(model, key)

    def test_update_own_memory_and_vector_only(self):
        asyncio.run(self.semantic_repo.update_memory(
            "semantic-a", "changed", self.changed_vector, agent_id="internal-a"
        ))
        self.assertEqual(self.record(semanticMemory, "semantic-a").content, "changed")
        self.assertEqual(list(self.record(memoryVector, "vector-semantic-a").embedding), self.changed_vector)
        self.assertEqual(self.record(semanticMemory, "semantic-b").content, "semantic-b")
        self.assertEqual(list(self.record(memoryVector, "vector-semantic-b").embedding), self.vector)
        self.assertEqual(self.adapter.commits, 0)

    def test_update_rejects_other_user_or_other_agent_of_same_user(self):
        for target in ("semantic-b", "semantic-a2"):
            with self.subTest(target=target), self.assertRaises(ValueError):
                asyncio.run(self.semantic_repo.update_memory(
                    target, "changed", self.changed_vector, agent_id="internal-a"
                ))
            self.assertEqual(self.record(semanticMemory, target).content, target)
            self.assertEqual(list(self.record(memoryVector, "vector-" + target).embedding), self.vector)

    def test_semantic_delete_keeps_dual_flags_and_rejects_other_owner(self):
        asyncio.run(self.semantic_repo.kill_memory("semantic-a", agent_id="internal-a"))
        own = self.record(semanticMemory, "semantic-a")
        self.assertTrue(own.is_delete)
        self.assertFalse(own.is_alive)
        for target in ("semantic-b", "semantic-a2"):
            with self.assertRaises(ValueError):
                asyncio.run(self.semantic_repo.kill_memory(target, agent_id="internal-a"))
            other = self.record(semanticMemory, target)
            self.assertFalse(other.is_delete)
            self.assertTrue(other.is_alive)
        self.assertEqual(self.adapter.commits, 0)

    def test_episodic_delete_is_scoped(self):
        asyncio.run(self.episode_repo.kill_memory("episode-a", agent_id="internal-a"))
        self.assertTrue(self.record(episodicMemory, "episode-a").is_delete)
        with self.assertRaises(ValueError):
            asyncio.run(self.episode_repo.kill_memory("episode-b", agent_id="internal-a"))
        self.assertFalse(self.record(episodicMemory, "episode-b").is_delete)

    def test_physical_delete_rejects_foreign_memory_before_removing_vectors(self):
        with self.assertRaises(ValueError):
            asyncio.run(self.semantic_repo.remove_memory("semantic-b", agent_id="internal-a"))
        self.assertIsNotNone(self.record(semanticMemory, "semantic-b"))
        self.assertIsNotNone(self.record(memoryVector, "vector-semantic-b"))
        asyncio.run(self.semantic_repo.remove_memory("semantic-a", agent_id="internal-a"))
        self.assertIsNone(self.record(semanticMemory, "semantic-a"))
        self.assertIsNone(self.record(memoryVector, "vector-semantic-a"))
        self.assertIsNone(self.session.get(Memory, "semantic-a"))
        self.assertEqual(self.adapter.commits, 1)

    def test_archive_rejects_entire_mixed_batch_and_archives_own_records(self):
        for repo, model, prefix in (
            (self.origin_repo, originContent, "origin"),
            (self.episode_repo, episodicMemory, "episode"),
        ):
            with self.subTest(model=prefix):
                with self.assertRaises(ValueError):
                    asyncio.run(repo.mark_archived([prefix + "-a", prefix + "-b"], agent_id="internal-a"))
                self.assertFalse(self.record(model, prefix + "-a").is_archive)
                self.assertFalse(self.record(model, prefix + "-b").is_archive)
                asyncio.run(repo.mark_archived([prefix + "-a", prefix + "-a"], agent_id="internal-a"))
                self.assertTrue(self.record(model, prefix + "-a").is_archive)
                self.assertFalse(self.record(model, prefix + "-b").is_archive)
                asyncio.run(repo.mark_archived([], agent_id="internal-a"))
        self.assertEqual(self.adapter.commits, 0)

    def test_wrong_type_and_nonexistent_memory_are_rejected(self):
        for target in ("episode-a", "missing", None):
            with self.subTest(target=target), self.assertRaises(ValueError):
                asyncio.run(self.semantic_repo.kill_memory(target, agent_id="internal-a"))
        with self.assertRaises(ValueError):
            asyncio.run(self.origin_repo.mark_archived(["episode-a"], agent_id="internal-a"))
        self.assertFalse(self.record(episodicMemory, "episode-a").is_delete)
        self.assertFalse(self.record(episodicMemory, "episode-a").is_archive)

    def test_write_scope_is_required_instead_of_optional_fallback(self):
        calls = [
            lambda: self.semantic_repo.update_memory("semantic-a", "changed", self.vector),
            lambda: self.semantic_repo.kill_memory("semantic-a"),
            lambda: self.semantic_repo.remove_memory("semantic-a"),
            lambda: self.episode_repo.kill_memory("episode-a"),
            lambda: self.episode_repo.mark_archived(["episode-a"]),
            lambda: self.origin_repo.mark_archived(["origin-a"]),
        ]
        for call in calls:
            with self.assertRaises(TypeError):
                call()

    def test_similarity_decisions_reject_other_agents_target(self):
        for action in ("UPDATE", "DELETE"):
            with self.subTest(action=action), self.assertRaises(ValueError):
                asyncio.run(consolidationService._apply_similarity_decisions(
                    self.semantic_repo, [(self.semantic_info(), {"action": action, "target_id": "semantic-b"})],
                    agent_id="internal-a",
                ))
            other = self.record(semanticMemory, "semantic-b")
            self.assertEqual(other.content, "semantic-b")
            self.assertFalse(other.is_delete)
            self.assertTrue(other.is_alive)

    def test_episode_sources_must_belong_to_same_agent_before_any_insert(self):
        with self.assertRaises(ValueError):
            asyncio.run(self.episode_repo.add_memory(
                [self.episode_info()], "internal-a", origin_content_ids={"0": "origin-b"}, commit=False
            ))
        self.assertFalse(self.session.new)
        self.assertEqual(len(self.session.scalars(select(episodicMemory)).all()), 3)
        self.assertEqual(len(self.session.scalars(select(memoryVector)).all()), 9)

    def test_memory_and_vector_cannot_have_different_owners(self):
        memory = semanticMemory(id="bad", agent_id="internal-b", content="bad", type="fact")
        with self.assertRaises(ValueError):
            asyncio.run(self.semantic_repo._add_with_vector(memory, "internal-a", self.semantic_info()))
        self.assertFalse(self.session.new)

    def test_valid_episodic_consolidation_keeps_single_commit_and_owned_source(self):
        origin = self.session.get(originContent, "origin-a")
        data = ([self.episode_info()], [], [origin], {"0": "origin-a"})
        with patch("service.consolidationService.create_session", return_value=self.adapter):
            asyncio.run(consolidationService.add_episodic_memory("internal-a", data))
        self.assertEqual(self.adapter.commits, 1)
        self.assertTrue(self.record(originContent, "origin-a").is_archive)
        self.assertFalse(self.record(originContent, "origin-b").is_archive)
        links = self.session.scalars(select(episodeOriginLink)).all()
        self.assertEqual(len(links), 1)
        self.assertEqual(links[0].origin_content_id, "origin-a")
        new_episode = self.session.get(episodicMemory, links[0].episode_id)
        self.assertEqual(new_episode.agent_id, "internal-a")

    def test_valid_semantic_consolidation_keeps_single_commit_and_scoped_archive(self):
        episode = self.session.get(episodicMemory, "episode-a")
        decisions = [(self.semantic_info(), {"action": "DELETE", "target_id": "semantic-a"})]
        with patch("service.consolidationService.create_session", return_value=self.adapter):
            asyncio.run(consolidationService.add_semantic_memory(
                ([self.semantic_info()], decisions, [episode]), "internal-a"
            ))
        self.assertEqual(self.adapter.commits, 1)
        self.assertTrue(self.record(episodicMemory, "episode-a").is_archive)
        self.assertFalse(self.record(episodicMemory, "episode-b").is_archive)
        self.assertTrue(self.record(semanticMemory, "semantic-a").is_delete)
        self.assertFalse(self.record(semanticMemory, "semantic-b").is_delete)

    def test_invalid_late_decision_rolls_back_earlier_write_in_both_consolidations(self):
        for kind in ("semantic", "episode"):
            with self.subTest(kind=kind):
                decisions = [
                    (self.semantic_info(), {"action": "UPDATE", "target_id": kind + "-a"}),
                    (self.semantic_info(), {"action": "DELETE", "target_id": kind + "-b"}),
                ]
                self.adapter.commits = 0
                with patch("service.consolidationService.create_session", return_value=self.adapter), \
                     self.assertRaises(ValueError):
                    if kind == "semantic":
                        episode = self.session.get(episodicMemory, "episode-a")
                        asyncio.run(consolidationService.add_semantic_memory(([], decisions, [episode]), "internal-a"))
                    else:
                        origin = self.session.get(originContent, "origin-a")
                        asyncio.run(consolidationService.add_episodic_memory("internal-a", ([], decisions, [origin], {})))
                self.assertEqual(self.adapter.commits, 0)
                model = semanticMemory if kind == "semantic" else episodicMemory
                self.assertEqual(self.record(model, kind + "-a").content, kind + "-a")
                self.assertFalse(self.record(model, kind + "-b").is_delete)
                self.assertFalse(self.record(originContent, "origin-a").is_archive)
                self.assertFalse(self.record(episodicMemory, "episode-a").is_archive)


if __name__ == "__main__":
    unittest.main()
