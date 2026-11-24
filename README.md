# MiniMemo

面向智能体的分层记忆系统。把原始对话落库，自动抽取成情景记忆和语义记忆，
对外提供向量 + 全文的多路检索。

Python 3.11+ / FastAPI / SQLAlchemy 2.x 异步 / PostgreSQL（pgvector + ParadeDB）/ RabbitMQ。

## 记忆分层

| 层级 | 内容 | 产生方式 |
|---|---|---|
| 原文 | 用户与智能体的原话 | 调用方写入 |
| 情景记忆 | 一件值得以后回忆的具体经历 | 从原文抽取 |
| 语义记忆 | 可复用的长期事实、偏好与约定 | 从情景记忆提炼 |

三层共用一张 `memory` 父表（joined 继承，`memory_type` 作鉴别器），
子表只放各自的特性字段。向量在 `memory_vector`，原文与情景记忆的溯源关系在
`episode_origin_link`。

## 快速开始

```bash
pip install -e ".[mcp]"
```

前置依赖：

- PostgreSQL，需装 `vector` 和 `pg_search` 两个扩展（启动时会自动 `CREATE EXTENSION`）
- RabbitMQ，需要 vhost `/MiniMemo`
- 在 `.env` 里填 `DB_DSN`、`MQ_PASSWORD` 和 `DEFAULT_*` 模型配置

启动两个进程：

```bash
python main.py       # API，监听 127.0.0.1:1314
python worker.py     # 记忆抽取进程
```

`main.py` 只负责落库和发触发信号，真正的抽取在 `worker.py` 里跑——
LLM 调用动辄数秒，放在 API 进程里会拖住事件循环。

> **Windows**：psycopg 的异步驱动不能用默认的 ProactorEventLoop，三个入口都做了处理
> （`main.py` 走 uvicorn 的 `loop="asyncio:SelectorEventLoop"`，其余用
> `asyncio.Runner(loop_factory=asyncio.SelectorEventLoop)`）。
> 另外 MQ 地址用 `127.0.0.1` 而不是 `localhost`：后者在 Windows 上优先解析成 `::1`，
> 而 5672 没听 IPv6，会静默超时很久。

## 使用

### HTTP 接口

| 方法 | 路径 | 作用 |
|---|---|---|
| POST | `/MiniMemo/memory/add` | 写入一条原文 |
| POST | `/MiniMemo/memory/search` | 检索记忆 |
| POST | `/MiniMemo/agent/register/{user_id}/{agent_name}` | 注册智能体 |
| GET | `/MiniMemo/agent/list/{user_id}` | 列出用户下的智能体 |
| POST | `/MiniMemo/session/register` | 注册会话 |
| POST | `/MiniMemo/user/register` | 注册用户 |
| POST | `/MiniMemo/model/add` · `set` · `delete` | 维护用户的模型配置 |
| POST | `/MiniMemo/consolidation/add_episodic_memory/...` | 手动触发情景抽取 |
| POST | `/MiniMemo/consolidation/add_semantinc_memory/...` | 手动触发语义提炼 |

正常情况下不需要手动触发抽取，`worker.py` 会按水位自动跑。

### MCP

`mcp_server.py` 把系统包成 MCP 工具，通过 HTTP 反向调用 MiniMemo API：

| 工具 | 作用 |
|---|---|
| `add_memory(content, session_id, role)` | 保存一条原文 |
| `search_memory(query)` | 检索已有记忆 |

需要环境变量 `MINIMEMO_USER_ID`、`MINIMEMO_AGENT_NAME`，
可选 `MINIMEMO_API_URL`（默认 `http://127.0.0.1:1314`）。

```bash
python mcp_server.py
```

### 聊天伴侣样例

`judgeMent/bot/` 是一个用这套记忆做的聊天伴侣，可直接运行：

```bash
python -m judgeMent.bot.talk
```

## 目录结构

```
main.py                  FastAPI 入口
worker.py                记忆抽取进程（消费者 + 兜底扫描器）
mcp_server.py            MCP 工具入口
log.py                   loguru 配置

config/                  参数与模型配置（敏感项从 .env 读）
common/                  pydantic 模型、请求体、统一响应 Result、业务异常
db/                      engine / session / 建表 / 手写 SQL 迁移
models/                  ORM 模型
repository/              数据访问层
service/                 写入、检索、抽取编排
mq/                      RabbitMQ 拓扑、生产者、消费者、水位判断
prompt/                  抽取与判重用的提示词
tools/                   BM25 检索、RRF 融合、行锁、后台任务
router/                  FastAPI 路由
judgeMent/               召回评测 + 聊天伴侣样例
```

## 评测

`judgeMent/tests/` 是四层召回评测，每层可单独运行：

```bash
python -m judgeMent.tests.layer1_vector --user-id USER --agent-id AGENT
python -m judgeMent.tests.layer2_bm25   --user-id USER --agent-id AGENT
python -m judgeMent.tests.layer3_rrf    --user-id USER --agent-id AGENT
python -m judgeMent.tests.layer4_rerank --user-id USER --agent-id AGENT
```

| 层 | 内容 |
|---|---|
| layer1 | 三路向量召回 |
| layer2 | BM25 召回 |
| layer3 | 四路 + RRF 融合 |
| layer4 | 叠加精排，与 RRF 对比 |

题集在 `judgeMent/question/recall_cases.json`，日志落 `judgeMent/testLog/`。
另有一个扫描融合参数的工具：`python -m judgeMent.tools.get_TOP_N`。
