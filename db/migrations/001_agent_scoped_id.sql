-- PostgreSQL：从全局 Agent 编号迁移为用户内唯一名称。
-- 前提：users 表和 agents.user_id 外键已建立，旧 Agent 的用户归属已补齐。
-- 保留 agents.id 及所有子表外键的原值，也保留队列中已有的内部标识。
-- 暂停 API/worker 后在目标数据库执行；整份脚本为一个事务。
BEGIN;

ALTER TABLE agents ADD COLUMN agent_name VARCHAR;
UPDATE agents SET agent_name = id;
ALTER TABLE agents ALTER COLUMN agent_name SET NOT NULL;
ALTER TABLE agents ADD CONSTRAINT uq_user_agent UNIQUE (user_id, agent_name);

COMMIT;
