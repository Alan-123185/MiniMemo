# Agent 标识

`users.user_id` 是用户表的唯一字段和主键。

`agents.id` 是自动生成的内部主键；`agents.agent_name` 是调用方填写的名称。
`(user_id, agent_name)` 联合唯一，因此不同用户可以创建同名 Agent。
会话、记忆、向量表中的 `agent_id` 外键仍引用 `agents.id`；后台任务和锁也使用内部主键。

## 接口参数

Agent 注册、列表、会话注册、记忆写入和搜索，以及主动提炼接口，均需要查询参数 `user_id`。
原有请求体或路径中的 `agent_name` 表示该用户下的对外名称。

例如，用户 `alice` 写入 `assistant` 的原文：

```http
POST /MiniMemo/memory/add?user_id=alice
Content-Type: application/json

{"agent_name":"assistant","origin_content":"一段对话","session_id":"default"}
```

接口先按用户和编号找到 Agent，再将内部主键交给原有业务函数。
找不到时返回 404，不回退到按内部主键或全局编号查找。
列表只返回该用户的对外编号。创建 Agent 前，需要先存在对应的用户记录。

这里的 `user_id` 延续现有接口的显式传参方式，尚未接入登录认证。
按用户定位数据并不能验证调用者身份；接入认证时应从可信身份中取得用户编号。
主动提炼路由目前没有在 `main.py` 挂载，本次维持该状态。

## 已有数据库

`create_all` 只会创建缺失的表，不会给现有 `agents` 表添加新列。
已有数据库需要单独执行 [迁移脚本](../db/migrations/001_agent_scoped_id.sql)。

执行前应暂停 API 和 worker，确认 `users` 表、`agents.user_id` 外键已经建立，
且已有 Agent 的用户归属均已补齐。本次不自动指定旧数据的用户归属，也不自动执行迁移。

脚本将旧的 `agents.id` 复制为对外 `agent_name`，保留旧主键及子表外键，
因此已有会话、记忆、向量和队列消息仍引用相同的内部记录。
新注册的 Agent 由应用自动生成 UUID 字符串作为内部主键。

## 非检索写操作的归属校验

更新、作废、物理删除及批量归档记忆时，必须通过关键字参数 `agent_id` 传入当前 Agent 的内部主键。
写入前检查目标记忆是否存在、类型是否匹配、是否属于该 Agent；校验失败抛出 `ValueError`。
批量归档会先校验整批 ID，不会忽略越界 ID 后继续归档。情景记忆关联的原文也必须属于同一个 Agent。
记忆与向量写入使用相同的内部主键。

提炼服务向上述写操作传递内部主键，校验异常沿用现有事务退出时的回滚行为。
后台扫描、消息队列和锁继续使用内部主键，不需要再次传递用户编号。
本次未调整任何记忆检索函数。
