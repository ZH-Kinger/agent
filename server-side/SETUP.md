# server-side — 云服务器部署

> 部署到你的云服务器，提供 AI Review + Jira + 飞书通知等 API

## 架构

```
云服务器 (Docker)
├── /health          → 健康检查
├── /review          → 单独的 AI Review（兼容旧接口）
├── /pr-pipeline     → 一站式处理：Jira + AI Review + 飞书通知
├── /mcp/sse         → MCP SSE 连接（Claude Code 远程接入）
└── /mcp/messages    → MCP 消息
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
```

### 3. 直接运行（开发调试）

```bash
cd mcp-server
pip install -e .
MCP_TRANSPORT=http python server.py
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
  "review": "## 🤖 AI Review ...",
  "jira_id": "DEMO-123",
  "jira_url": "https://jira.wuji.tech/browse/DEMO-123",
  "has_blocker": false,
  "steps": [
    "✅ Jira 工单已创建: DEMO-123",
    "✅ AI Review 完成",
    "✅ 飞书通知已发送"
  ]
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
├── cli.py                 # CLI 工具（不依赖 Claude）
├── pyproject.toml         # Python 依赖
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

- `REVIEW_TOKEN` 用于 GitHub Actions → 服务器的鉴权
- 所有敏感信息在 `.env` 中，不入 Git
- Docker 容器内运行，不暴露多余端口
- 建议在前面加 Nginx 反向代理 + HTTPS
