# wuji-technology/.github

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

wuji-technology 组织的自动化协作平台，包含 **PR 自动 Review**、**Jira 工单管理**、**飞书通知**、**Release 自动化**等能力。

项目拆分为两个独立部署单元：
- **`github-side/`** — 放到各 GitHub 仓库，轻量触发
- **`server-side/`** — 部署到云服务器，承担 AI 推理和集成

---

## 目录

- [架构总览](#架构总览)
- [项目结构](#项目结构)
- [核心流程](#核心流程)
  - [流程一：PR 自动 Review](#流程一pr-自动-review)
  - [流程二：Release 自动化](#流程二release-自动化)
- [部署指南](#部署指南)
  - [服务器端部署](#服务器端部署)
  - [GitHub 端部署](#github-端部署)
- [本地开发者工具（MCP & CLI）](#本地开发者工具mcp--cli)
- [配置要求](#配置要求)
- [代码规范](#代码规范)

---

## 架构总览

```
开发者本地                     GitHub 服务器                    云服务器
┌──────────────┐         ┌─────────────────────┐         ┌──────────────────────┐
│              │  Push PR │                     │  curl   │                      │
│  Claude Code │────────→│  GitHub Actions      │───────→│  wuji Review Server  │
│  (本地 diff) │         │  ┌─ Convention Check │        │  ┌─ AI Review (Qwen) │
│              │         │  └─ curl 转发        │←───────│  ├─ Jira 创建/回写    │
└──────────────┘         │     ↓                │ result │  └─ 飞书通知          │
                         │  Post PR Comment     │        │                      │
                         └─────────────────────┘        └──────────────────────┘
                           github-side/                     server-side/
                           (免费)                           (DashScope API 费用)
```

---

## 项目结构

```
├── github-side/                       ← Part 1: 放到各 GitHub 仓库的 .github/
│   ├── workflows/
│   │   ├── ci-pr-pipeline.yml         # PR 触发：规范检查 + 调云服务器 AI Review
│   │   └── release-auto.yml           # Tag 触发：自动创建 GitHub Release
│   └── SETUP.md                       # GitHub 端部署说明
│
├── server-side/                       ← Part 2: 部署到云服务器
│   ├── Dockerfile                     # Docker 镜像
│   ├── docker-compose.yml             # 一键启动
│   ├── .env.example                   # 环境变量模板
│   └── SETUP.md                       # 服务器端部署说明
│
├── mcp-server/                        ← 核心代码（被 server-side/ 打包）
│   ├── server.py                      # HTTP Server + MCP Server
│   ├── config.py                      # 配置中心（所有环境变量）
│   ├── cli.py                         # 独立 CLI（不依赖 Claude）
│   ├── pyproject.toml                 # Python 依赖
│   └── tools/
│       ├── review.py                  # 多 Agent AI Review（Qwen-Max）
│       ├── jira.py                    # Jira 工单：查询、创建、状态更新
│       ├── feishu.py                  # 飞书卡片通知
│       ├── changelog.py              # CHANGELOG 预览
│       ├── fetch.py                   # 从 GitHub 抓取 CHANGELOG
│       ├── github_actions.py          # 触发 GitHub Actions
│       ├── validate.py                # 格式校验
│       └── versions.py               # 版本查询与自动推断
│
├── scripts/
│   ├── release/                       # 发版辅助脚本
│   ├── docs/                          # 文档收集脚本
│   ├── notify/                        # 通知脚本
│   └── tests/
│
├── .github/                           # 本仓库自身的 CI
│   ├── actions/                       # 可复用 composite actions
│   └── workflows/                     # 本仓库的 workflow
│
├── actions/
│   └── auto-release/                  # 解析 CHANGELOG 创建 GitHub Release
│
└── profile/
    └── README.md                      # 组织 Profile 首页
```

---

## 核心流程

### 流程一：PR 自动 Review

开发者提交 PR 后自动触发，全流程无需人工干预：

```
① 开发者本地
   Claude Code 辅助 diff（可选，开发者自己的 Key）
   git push + 创建 PR

② GitHub Actions 自动触发（github-side/workflows/ci-pr-pipeline.yml）
   ┌─────────────────────────────────────────────┐
   │ Job 1: PR Convention Check（几秒，免费）      │
   │  · 标题是否 Conventional Commits 格式        │
   │  · 描述是否关联 Resolve m-xxx / f-xxx        │
   └─────────────────────────────────────────────┘
   ┌─────────────────────────────────────────────┐
   │ Job 2: AI Review（1-2分钟）                  │
   │  · curl → 云服务器 /pr-pipeline              │
   │  · 服务器返回结果 → 评论到 PR                 │
   └─────────────────────────────────────────────┘

③ 云服务器 /pr-pipeline 执行（server-side/）
   ┌─────────────────────────────────────────────┐
   │ Step 1: 自动创建 Jira 工单                    │
   │   · feat → Story, fix → Bug, 其余 → Task    │
   │   · 如果 PR 已关联 Jira ID 则跳过            │
   │                                              │
   │ Step 2: 多 Agent AI Review（Qwen-Max）       │
   │   · Agent A（并行）🔐 安全与正确性            │
   │   · Agent B（并行）🏗️ 架构与可维护性          │
   │   · 综合对比 Agent → 最终报告                 │
   │   · 拉取 Jira 验收标准，对照审查              │
   │                                              │
   │ Step 3: 飞书卡片通知                          │
   │   · 发送 Review 结果到飞书群                  │
   │   · Blocker → 红色卡片, 通过 → 绿色卡片      │
   └─────────────────────────────────────────────┘

④ PR 页面显示结果
   ✅ PR Convention Check — passed
   ✅ AI Review — 评论已发布（含 Jira 链接）

⑤ Reviewer 人工审核（可选）→ Approve → 合并
   → GitHub 自动删除开发分支
```

**LLM 后端**：通过 OpenAI 兼容接口对接阿里云 DashScope（Qwen-Max），所有 API Key 集中在服务器端管理。

---

### 流程二：Release 自动化

```
① 触发（GitHub Actions 手动 或 Claude Code 对话 或 CLI）
   输入：wujihandpy=1.6.0
         wujihandros2=2.0.0

   MCP suggest_next_version 可自动推断版本号：
   · Unreleased 含 Added/新增   → minor bump（1.5.0 → 1.6.0）
   · Unreleased 含 Fixed/修复   → patch bump（1.5.0 → 1.5.1）
   · Unreleased 含 Removed/破坏 → major bump（1.5.0 → 2.0.0）

② release-centralized.yml
   · 更新各仓库 CHANGELOG.md（Unreleased → vX.Y.Z）
   · 更新 .release.yml 配置的版本号文件
   · 创建 release/vX.Y.Z 分支 + PR（auto-release label）
   · 飞书通知

③ 人工审核 PR → 合并

④ release-auto-on-pr.yml
   检测 auto-release label + release/v* → 自动打 git tag

⑤ release-auto.yml（github-side/workflows/）
   tag push → 解析 CHANGELOG → 创建 GitHub Release
```

---

## 部署指南

### 服务器端部署

> 详细说明见 [server-side/SETUP.md](server-side/SETUP.md)

```bash
# 1. 准备环境变量
cd server-side
cp .env.example .env
# 编辑 .env，填入真实配置

# 2. Docker 启动
docker compose up -d

# 3. 验证
curl http://localhost:8080/health  # → "ok"
```

**API 端点：**

| 端点 | 方法 | 用途 |
|------|------|------|
| `/health` | GET | 健康检查 |
| `/pr-pipeline` | POST | 一站式：Jira + AI Review + 飞书通知 |
| `/review` | POST | 单独的 AI Review（兼容旧接口） |
| `/mcp/sse` | GET | Claude Code MCP SSE 连接 |

### GitHub 端部署

> 详细说明见 [github-side/SETUP.md](github-side/SETUP.md)

```bash
# 1. 复制 workflow 到你的仓库
cp github-side/workflows/*.yml your-repo/.github/workflows/

# 2. 配置仓库 Secrets（Settings → Secrets → Actions）
#    REVIEW_SERVER_URL = http://your-server:8080
#    REVIEW_TOKEN      = 与 server-side/.env 中一致
```

---

## 本地开发者工具（MCP & CLI）

### 安装

```bash
cd mcp-server
pip install -e .
```

### 方式一：Claude Code + MCP（推荐）

在 `.mcp.json` 中配置（stdio 模式，本地运行）：

```json
{
  "mcpServers": {
    "wuji-release": {
      "type": "stdio",
      "command": "python",
      "args": ["/path/to/mcp-server/server.py"],
      "env": { "GITHUB_TOKEN": "${GITHUB_TOKEN}" }
    }
  }
}
```

或连接已部署的服务器（SSE 模式）：

```json
{
  "mcpServers": {
    "wuji-release": {
      "type": "sse",
      "url": "http://your-server:8080/mcp/sse"
    }
  }
}
```

之后在 Claude Code 中对话：

```
> 现在各仓库版本是多少？
> wujihandpy 下一版该发什么？
> 帮我 dry run 发 wujihandpy=1.6.0
> 确认，正式发
```

### 方式二：CLI 命令行

```bash
wuji-release versions                    # 查询各仓库当前版本
wuji-release next-version wujihandpy     # 推断下一版本号
wuji-release validate "wujihandpy=1.6.0" # 校验格式
wuji-release trigger "wujihandpy=1.6.0" --dry-run  # 预览
wuji-release trigger "wujihandpy=1.6.0"  # 正式触发
wuji-release status                      # 查看 workflow 状态
wuji-release fetch wujihandpy 1.5.0      # 查看某版本 CHANGELOG
```

---

## 配置要求

### 云服务器环境变量（server-side/.env）

| 环境变量 | 必填 | 用途 |
|----------|:---:|------|
| `GITHUB_TOKEN` | ✅ | 拉取 PR diff、版本信息、评论 PR |
| `GITHUB_ORG` | ✅ | GitHub 组织名（默认 wuji-technology） |
| `OPENAI_API_KEY` | ✅ | DashScope API Key（Qwen-Max） |
| `OPENAI_BASE_URL` | ✅ | `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| `LLM_MODEL` | | LLM 模型名（默认 qwen-max） |
| `LLM_MAX_TOKENS` | | 最大 token 数（默认 2048） |
| `REVIEW_TOKEN` | ✅ | GitHub Actions 调用鉴权 |
| `MCP_TRANSPORT` | | 设为 `http` 启动 HTTP 模式 |
| `MCP_PORT` | | 监听端口（默认 8080） |
| `JIRA_URL` | | Jira 地址（如 `https://jira.wuji.tech`） |
| `JIRA_PAT` | | Jira Personal Access Token |
| `JIRA_PROJECT_KEY` | | Jira 项目 Key（默认 DEMO） |
| `FEISHU_APP_ID` | | 飞书应用 ID |
| `FEISHU_APP_SECRET` | | 飞书应用密钥 |
| `FEISHU_CHAT_ID` | | 飞书群 ID |

### GitHub 仓库 Secrets

| Secret | 用途 |
|--------|------|
| `REVIEW_SERVER_URL` | 云服务器地址（如 `http://your-server:8080`） |
| `REVIEW_TOKEN` | 与服务器端 `.env` 中保持一致 |

> `GITHUB_TOKEN` 由 GitHub Actions 自动提供，无需手动配置。

### 各开发者本地

```bash
# ~/.bashrc 或 ~/.zshrc
export GITHUB_TOKEN=ghp_xxx   # GitHub PAT，有组织读写权限
```

---

## 代码规范

### 分支命名

```
feat/m-123456-grasp-detection     # 新功能
fix/f-654321-calibration-error    # Bug 修复
docs/update-readme                # 文档
```

### Commit 规范（Conventional Commits）

```
feat(detection): add grasp pose estimation module
fix(calibration): resolve hand tracking drift issue
docs: update deployment guide
```

### PR 规范

- **标题**：遵循 Conventional Commits 格式
- **描述**：包含 `Resolve m-123456` 或 `Resolve f-654321` 关联工作项
- **CHANGELOG**：非 docs/chore PR 需更新 `## [Unreleased]` 段落
- **合并后**：自动删除开发分支

### CHANGELOG 格式

```markdown
## [Unreleased]

### Added
- 新功能描述

### Fixed
- Bug 修复描述

## [1.5.0] - 2026-04-23
...
```

---

## Contact

dev@wuji.tech
