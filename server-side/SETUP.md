# server-side — 云服务器部署

> 部署到你的云服务器，提供 AI Review + Jira + 飞书通知 + Token 签发等 API

## 架构

```
云服务器 (Docker)
├── /health                   → 存活检查
├── /ready                    → 运行状态摘要（脱敏）
├── /debug/config             → 配置摘要（脱敏）
├── /review                   → 单独的 AI Review（兼容旧接口）
├── /pr-pipeline              → 一站式处理：Jira + AI Review + 飞书通知
├── /bootstrap/register-repo  → 初始化时为仓库签发专属 REVIEW_TOKEN
├── /mcp/sse                  → MCP SSE 连接（Claude Code 远端接入）
└── /mcp/messages             → MCP 消息
```

## 快速部署

### 1. 准备环境变量

```bash
cd server-side
cp .env.example .env
# 编辑 .env，填入真实的 Token 和密钥
```

### 2. Docker 部署（推荐）

```bash
# 在 server-side/ 目录下
docker compose up -d

# 查看日志
docker logs -f wuji-review-server

# 验证健康
curl http://localhost:8080/health
curl http://localhost:8080/ready
curl http://localhost:8080/debug/config
```

### 3. 直接运行（开发调试）

```bash
cd mcp-server
pip install -e .
MCP_TRANSPORT=http python server.py
```

## 环境变量说明

### GitHub

| 变量 | 说明 | 示例 |
|------|------|------|
| `GITHUB_TOKEN` | GitHub PAT，需有 repo 权限 | `ghp_xxxx` |
| `GITHUB_ORG` | 组织名 | `wuji-technology` |

### LLM（AI Review 核心）

| 变量 | 说明 | 示例 |
|------|------|------|
| `OPENAI_API_KEY` | 阿里云 DashScope API Key | `sk-xxxx` |
| `OPENAI_BASE_URL` | DashScope 兼容接口 | `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| `LLM_MODEL` | 使用的模型 | `qwen-max` |
| `LLM_MAX_TOKENS` | 最大输出 token | `2048` |

### Jira（可选）

| 变量 | 说明 | 示例 |
|------|------|------|
| `JIRA_URL` | Jira 地址 | `https://jira.wuji.tech` |
| `JIRA_PAT` | Personal Access Token | `xxxx` |
| `JIRA_PROJECT_KEY` | 项目 Key | `DEMO` |
| `JIRA_ISSUE_TYPE` | 工单类型 | `Task` |
| `JIRA_SYNC_TO_JIRA` | 是否自动同步到 Jira | `true` / `false` |

### 飞书（可选）

| 变量 | 说明 | 示例 |
|------|------|------|
| `FEISHU_APP_ID` | 飞书应用 ID | `cli_xxxx` |
| `FEISHU_APP_SECRET` | 飞书应用 Secret | `xxxx` |
| `FEISHU_CHAT_ID` | 飞书群聊 ID | `oc_xxxx` |

### MCP Server

| 变量 | 说明 | 示例 |
|------|------|------|
| `MCP_TRANSPORT` | 传输方式 | `http`（服务器部署）/ `stdio`（本地） |
| `MCP_PORT` | HTTP 端口 | `8080` |
| `REVIEW_TOKEN` | 全局共享鉴权 Token（所有仓库共用，旧模式） | `your-secret-token` |
| `BOOTSTRAP_TOKEN` | 管理员初始化口令，用于签发仓库专属 token | `wuji1234` |
| `REPO_TOKENS_FILE` | 仓库专属 token 的持久化文件路径 | `/data/repo_tokens.json` |

### Token 模式说明

服务端支持两种 REVIEW_TOKEN 鉴权模式：

**旧模式（全局共享）**：只配 `REVIEW_TOKEN`，所有仓库共用同一个 token。

**新模式（仓库专属）**：配 `BOOTSTRAP_TOKEN` + `REPO_TOKENS_FILE`，每个仓库有自己的 `wr_xxxx` token。

两种模式可共存：服务端会先查仓库专属 token，没有则回退到全局 `REVIEW_TOKEN`。

## 诊断与排障

### 基础自检

```bash
curl http://localhost:8080/health      # 服务是否存活
curl http://localhost:8080/ready       # 运行状态摘要
curl http://localhost:8080/debug/config  # 检查各模块是否启用
curl -i http://localhost:8080/mcp/sse  # 验证 MCP SSE 连接
```

- `/health`：服务是否存活
- `/ready`：返回脱敏后的运行状态摘要
- `/debug/config`：检查 transport、port、Jira/Feishu 是否启用
- `/mcp/sse`：验证远端 MCP 入口是否正常建立连接
- `/bootstrap/register-repo`：验证初始化签发链路是否已启用（需 `BOOTSTRAP_TOKEN`）

### 查看日志

```bash
docker logs --tail 200 wuji-review-server
```

重点关注：
- `sse connect failed`
- `review failed`
- `pipeline review failed`
- `jira create failed`
- `feishu notify failed`

### 反向代理注意事项

如果前面挂了 Nginx / HTTPS 反代，SSE 需要保留长连接并关闭缓冲，否则 `/mcp/sse` 可能异常：

- 关闭 proxy buffering
- 保留 `Connection` / `Cache-Control` 相关头
- 提高 read timeout
- 确保公网可访问 `/mcp/sse` 和 `/mcp/messages`

### 更新部署

当代码更新后，重新构建并启动：

```bash
cd server-side
docker compose up -d --build
```

如果从 GitHub 拉取代码有网络问题（服务器在国内），可以在本地打包上传：

```bash
# 本地
tar czf /tmp/wuji-update.tar.gz mcp-server server-side scripts
scp /tmp/wuji-update.tar.gz root@<服务器IP>:/tmp/

# 服务器
cd /root/wuji-github
tar xzf /tmp/wuji-update.tar.gz
cd server-side && docker compose up -d --build
```

## API 端点

### POST /pr-pipeline

GitHub Actions 调用的主端点。一次请求完成全部流程。

**Headers:**
```
Authorization: Bearer <REVIEW_TOKEN>
Content-Type: application/json
```

**Body:**
```json
{
  "repo": "wujihandpy",
  "pr_number": 42,
  "title": "feat(detection): add grasp module",
  "body": "Resolve m-123456",
  "org": "wuji-technology",
  "language": "zh"
}
```

**Response:**
```json
{
  "review": "## AI Review ...",
  "jira_id": "DEMO-123",
  "jira_url": "https://jira.wuji.tech/browse/DEMO-123",
  "has_blocker": false,
  "steps": [
    "Jira 工单已创建: DEMO-123",
    "AI Review 完成",
    "飞书通知已发送"
  ]
}
```

### POST /bootstrap/register-repo

初始化命令 `wuji-review init` 调用的注册端点，用于为当前仓库签发专属 `REVIEW_TOKEN`。

**Headers:**
```
Authorization: Bearer <BOOTSTRAP_TOKEN>
Content-Type: application/json
```

**Body:**
```json
{
  "repo_full_name": "wuji-technology/wujihandpy"
}
```

**Response:**
```json
{
  "ok": true,
  "repo_full_name": "wuji-technology/wujihandpy",
  "review_token": "wr_xxxxx",
  "request_id": "bootstrap-1712345678901"
}
```

### POST /review

单独的 AI Review 端点（不含 Jira 和飞书）。

**Body:**
```json
{
  "repo": "wujihandpy",
  "pr_number": 42,
  "title": "feat: xxx",
  "body": "...",
  "language": "zh"
}
```

## 代码结构

```
mcp-server/
├── server.py              # 入口：HTTP Server + MCP Server
├── config.py              # 所有环境变量配置
├── cli.py                 # CLI 工具（init / doctor / release）
├── pyproject.toml         # Python 依赖
├── templates/
│   └── ci-pr-pipeline.yml # PR Pipeline workflow 模板
└── tools/
    ├── review.py          # 多 Agent AI Review（Qwen-Max）
    ├── jira.py            # Jira 工单：查询、创建、状态更新
    ├── feishu.py          # 飞书卡片通知
    ├── changelog.py       # CHANGELOG 预览
    ├── fetch.py           # 从 GitHub 抓取 CHANGELOG
    ├── github_actions.py  # 触发 GitHub Actions
    ├── validate.py        # 校验 repo=version 格式
    └── versions.py        # 版本查询与推断
```

## 安全

- `BOOTSTRAP_TOKEN` 用于 `wuji-review init` 注册新仓库时的鉴权，只有管理员持有
- `REVIEW_TOKEN`（全局或仓库专属）用于 GitHub Actions → 服务器的鉴权
- 所有敏感信息在 `.env` 中，不入 Git
- Docker 容器内运行，不暴露多余端口
- 建议在前面加 Nginx 反向代理 + HTTPS
