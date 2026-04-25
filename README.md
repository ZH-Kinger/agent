# wuji-technology/.github

面向研发团队的自动化协作平台：把 **PR 规范检查、AI Review、Jira、飞书通知、Release 自动化、Claude Code MCP** 串成一套可复用能力。

## 先看哪一部分

### 我要给一个业务仓库接入 PR 自动 Review
- 5 分钟上手：[`github-side/QUICKSTART.md`](github-side/QUICKSTART.md)
- 完整接入说明：[`github-side/SETUP.md`](github-side/SETUP.md)
- 要复制的 workflow：[`github-side/workflows/ci-pr-pipeline.yml`](github-side/workflows/ci-pr-pipeline.yml)

### 我要部署或排障服务端
- 部署与诊断：[`server-side/SETUP.md`](server-side/SETUP.md)
- 运行入口：[`mcp-server/server.py`](mcp-server/server.py)
- Docker 配置：[`server-side/docker-compose.yml`](server-side/docker-compose.yml)

### 我要在 Claude Code 里连接 MCP
- MCP 使用说明：[`mcp-server/README.md`](mcp-server/README.md)
- 远端入口：`/mcp/sse`
- 本地 stdio 入口：`python mcp-server/server.py`

### 我要了解自动发版能力
- 说明文档：[`docs/release-automation.md`](docs/release-automation.md)
- MCP 工具实现：[`mcp-server/server.py`](mcp-server/server.py)

---

## 5 分钟快速开始

如果你的目标是“先让一个业务仓库用起来”，现在优先用初始化命令：

```bash
pip install -e ./mcp-server
wuji-review init --server-url http://<服务器IP>:8080 --bootstrap-token <BOOTSTRAP_TOKEN>
```

它会自动完成：

- 写入 `.github/workflows/ci-pr-pipeline.yml`
- 写入 `.mcp.json`，让 Claude Code 直接可连
- 检查 `gh auth status`
- 识别当前 GitHub 仓库
- 调服务端 `/bootstrap/register-repo` 申请当前仓库专属 `REVIEW_TOKEN`
- 在可用时自动写入 `REVIEW_SERVER_URL`、`REVIEW_TOKEN` 到 GitHub Secrets
- 检查服务端 `/health`
- 输出测试 PR 的下一步

如果你只想先手动接入，也可以走下面这条路径：

1. 在云服务器部署 Review Server：看 [`server-side/SETUP.md`](server-side/SETUP.md)
2. 复制 [`github-side/workflows/ci-pr-pipeline.yml`](github-side/workflows/ci-pr-pipeline.yml) 到目标仓库
3. 在目标仓库配置两个 Secrets：
   - `REVIEW_SERVER_URL`
   - `REVIEW_TOKEN`
4. 提一个测试 PR，等待 1-2 分钟
5. 确认 PR 页面出现规范检查与 AI Review 评论

更短的操作版说明见：[`github-side/QUICKSTART.md`](github-side/QUICKSTART.md)

---

## 这个仓库包含什么

### 1. GitHub Integration
放到业务仓库里，负责触发自动化流程。

- PR 标题规范检查
- PR 描述中的工作项引用检查
- 调用云服务器 `/pr-pipeline`
- 把 AI Review 结果回帖到 PR

目录：`github-side/`

### 2. Review Server
部署到云服务器，负责执行真正的自动化能力。

- `/review`：单独 AI Review
- `/pr-pipeline`：Jira + AI Review + 飞书通知
- `/mcp/sse`：远端 MCP 连接入口
- `/health`、`/ready`、`/debug/config`：健康检查与诊断

目录：`server-side/`、`mcp-server/`

### 3. MCP Tools
给 Claude Code 或 CLI 用的工具层。

- `get_current_versions`
- `suggest_next_version`
- `preview_changelog`
- `trigger_release`
- `get_workflow_status`

入口说明：[`mcp-server/README.md`](mcp-server/README.md)

### 4. Release Automation
统一做版本推断、CHANGELOG 预览、批量触发 release workflow。

说明文档：[`docs/release-automation.md`](docs/release-automation.md)

---

## 核心架构

```text
开发者 / Claude Code
        │
        │ 提交 PR / 调用 MCP
        ▼
GitHub Actions（业务仓库）
        │
        │ POST /pr-pipeline
        ▼
Review Server（云服务器）
   ├── AI Review
   ├── Jira 创建 / 关联
   ├── 飞书通知
   └── MCP SSE
```

---

## 常用入口

### 服务端接口

| 端点 | 方法 | 用途 |
|------|------|------|
| `/health` | GET | 存活检查 |
| `/ready` | GET | 返回脱敏运行状态 |
| `/debug/config` | GET | 查看 transport / port / Jira / Feishu 等配置摘要 |
| `/review` | POST | 单独执行 AI Review |
| `/pr-pipeline` | POST | 执行 Jira + AI Review + 飞书通知 |
| `/mcp/sse` | GET | Claude Code 远端 MCP SSE 连接 |
| `/mcp/messages` | POST | MCP 消息通道 |

### 最常用目录

```text
github-side/     业务仓库接入
server-side/     服务端部署
mcp-server/      MCP 与 CLI 核心实现
docs/            独立专题文档
```

---

## 接入后用户能获得什么

业务仓库接入后，开发者提 PR 会自动得到：

- PR 标题规范检查
- 工作项引用检查
- AI Review 评论
- 可选的 Jira 自动建单
- 可选的飞书群通知

平台维护者额外可以获得：

- 远端 MCP 接入 Claude Code
- 版本查询与下一版本推断
- Release dry-run 与正式触发

---

## 排障起点

如果接入后出问题，按这个顺序查：

1. `GET /health`
2. `GET /ready`
3. `GET /debug/config`
4. `GET /mcp/sse`
5. `docker logs --tail 200 wuji-review-server`

详细排障说明见：[`server-side/SETUP.md`](server-side/SETUP.md)

---

## 仓库结构

```text
github-side/
├── QUICKSTART.md
├── SETUP.md
└── workflows/
    └── ci-pr-pipeline.yml

server-side/
├── Dockerfile
├── docker-compose.yml
└── SETUP.md

mcp-server/
├── README.md
├── server.py
├── config.py
└── tools/

docs/
└── release-automation.md
```
