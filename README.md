# wuji-technology/.github

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

wuji-technology 组织的集中式 GitHub 配置仓库，包含共享 Workflow、可复用 Action、Release 自动化脚本，以及 MCP Server / CLI 工具。

---

## 目录

- [项目结构](#项目结构)
- [流程一：PR 自动 Review](#流程一pr-自动-review)
- [流程二：Release 自动化](#流程二release-自动化)
- [流程三：本地开发者工具（MCP & CLI）](#流程三本地开发者工具mcp--cli)
- [子仓库接入](#子仓库接入)
- [脚本说明](#脚本说明)
- [配置要求](#配置要求)

---

## 项目结构

```
├── .github/
│   ├── actions/
│   │   ├── claude-review/              # 快速 AI review（diff + API）
│   │   └── claude-agent-review/        # 深度多 Agent review（主动探索代码库）
│   └── workflows/
│       ├── ci-pr-check.yml             # 脚本单测 + YAML 格式校验
│       ├── ci-pr-review.yml            # 快速 Claude PR review
│       ├── ci-pr-agent-review.yml      # 多 Agent 深度 PR review
│       ├── release-centralized.yml     # 批量发版入口
│       ├── release-auto-on-pr.yml      # PR 合并 → 自动打 tag
│       ├── release-auto.yml            # tag push → GitHub Release
│       ├── docs-collect-changelogs.yml # 收集 CHANGELOG → 文档站 PR
│       └── maintenance-update-profile.yml
├── actions/
│   └── auto-release/                   # 解析 CHANGELOG 创建 GitHub Release
├── mcp-server/                         # MCP Server & CLI 工具
│   ├── server.py                       # MCP Server（stdio / HTTP + /review 端点）
│   ├── cli.py                          # 独立 CLI（不依赖 Claude）
│   └── tools/
│       ├── review.py                   # 多 Agent PR Review（服务器端）
│       ├── versions.py                 # 版本查询 & 自动推断
│       ├── github_actions.py           # 触发 workflow & 查状态
│       ├── changelog.py                # CHANGELOG 预览
│       ├── fetch.py                    # 抓取指定版本 CHANGELOG
│       └── validate.py                 # 格式校验
├── profile/
│   └── README.md                       # 组织 Profile 首页
└── scripts/
    ├── release/
    │   ├── parse-repos.py              # 解析 repo=version 输入
    │   ├── update-changelog.py         # Unreleased → vX.Y.Z
    │   └── update-versions.py          # 按 .release.yml 更新版本文件
    ├── docs/
    │   ├── fetch-changelogs.py
    │   ├── generate-release-template.py
    │   └── release-notes-config.json
    ├── notify/
    │   └── feishu-notify.py
    └── tests/
        └── test_parse_repos.py
```

---

## 流程一：PR 自动 Review

PR 提交后自动触发两种 review，并行运行：

### 快速 Review（`ci-pr-review.yml`，~10s）

1. **本地规范检查**（无 API 费用）
   - 标题格式：`feat` / `fix` / `docs` / `chore` 等 Conventional Commits 前缀
   - 描述含工作项关联：`Resolve m-xxx` 或 `Resolve f-xxx`
   - 非 `docs`/`chore` PR 是否更新了 `CHANGELOG.md`
2. **Claude API 分析 diff** → 输出 Blocker / High / Medium / Low 问题表格

### 深度多 Agent Review（`ci-pr-agent-review.yml`，1-3min）

**前置依赖**：PR 描述含工作项备份如 `Resolve JIRA-123`（支持 Jira 子的常规 ID 格式）。

GitHub Actions 只做一次 `curl`，实际推理全部在 Review 服务器上完成：

```
GitHub Actions（仅 curl + post comment + 可选 Jira 写）
        │
        ▼
Review Server（MCP Server HTTP 模式）
        │
        ├── ① 拉 Jira 验收标准（自动）
        │     · 提取 PR 里的 JIRA-123 → 拉取 AC/测试备注 → 注入给两个 Agent
        │     · 让安全 Agent 按“验收标准”审查而不仅是 diff
        │
        ├── Agent A（并行）  🔐 安全与正确性（页数 + 验收标准）
        │   · 注入/漏洞/权限
        │   · 边界条件/竞态
        │   · 错误处理/依赖安全
        │
        └── Agent B（并行）  🏗️  架构与可维护性
            · 职责单一/接口清晰
            · 重复代码/命名/测试
            · 性能/扩展性
                    │
                    ▼
              综合对比 Agent
              · ⚡ 共识问题 — 两个 Agent 都提，高置信度
              · 📋 单方问题 — 标注来源
              · 📌 合入建议 — 可合入 / 修 Blocker 后合 / 需大改
                    │
                    ▼
              Jira 回写（可选，配置 server env JIRA_SYNC_TO_JIRA=true）
              · 发现 Blocker → 自动退回 To Do + 卡 Review 点
              · 无 Blocker → 仅追加 Review 阵度（不改状态）
                    │
                    ▼
        GitHub Actions（发 PR 评论）
```

**GitHub Actions 无需配置 `ANTHROPIC_API_KEY`**，所有 Claude 调用在服务器端完成。

---

## 流程二：Release 自动化

```
① 触发（GitHub Actions 手动 或 Claude Code 对话）
   输入：wujihandpy=1.6.0
         wujihandros2=2.0.0
         wuji-retargeting-private=0.2.0:public/CHANGELOG.md

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

⑤ release-auto.yml
   tag push → 解析 CHANGELOG → 创建 GitHub Release → 飞书通知

⑥ docs-collect-changelogs.yml（由 ② 串联自动触发）
   收集各仓库 CHANGELOG → 生成 release-notes.mdx
   → wuji-docs-center 创建 PR
```

**子仓库 `.release.yml` 格式**（可选，用于自动更新版本文件）：

```yaml
version_files:
  - path: pyproject.toml
    pattern: '(version = ")(\d+\.\d+\.\d+)(")'
  - path: src/version.py
    pattern: '(__version__ = ")(\d+\.\d+\.\d+)(")'
```

---

## 流程三：本地开发者工具（MCP & CLI）

### 安装

```bash
cd mcp-server
pip install -e .
```

### 方式一：Claude Code + MCP（推荐，自然语言操作）

在 `.mcp.json`（提交到仓库，团队共享）中配置：

```json
{
  "mcpServers": {
    "wuji-release": {
      "type": "stdio",
      "command": "python",
      "args": ["/path/to/.github/mcp-server/server.py"],
      "env": { "GITHUB_TOKEN": "${GITHUB_TOKEN}" }
    }
  }
}
```

之后直接在 Claude Code 中对话：

```
> 现在各仓库版本是多少？
> wujihandpy 下一版该发什么？
> 帮我 dry run 发 wujihandpy=1.6.0
> 确认，正式发
> 最近发版有失败的吗？
```

### 方式二：CLI 命令行

```bash
# 查询各仓库当前版本
wuji-release versions
wuji-release versions wujihandpy wujihandros2

# 推断下一版本号
wuji-release next-version wujihandpy

# 校验格式
wuji-release validate $'wujihandpy=1.6.0\nwujihandros2=2.0.0'

# Dry run 预览
wuji-release trigger $'wujihandpy=1.6.0' --dry-run

# 正式触发发版
wuji-release trigger $'wujihandpy=1.6.0\nwujihandros2=2.0.0' --date 2026-05-01

# 查看 workflow 状态
wuji-release status
wuji-release status --workflow docs-collect-changelogs.yml --limit 3

# 查看某版本 CHANGELOG
wuji-release fetch wujihandpy 1.5.0
```

### 方式三：HTTP Server（团队共用，无需本地安装）

服务器同时承担两个职责：**MCP Server**（给 Claude Code 用）和 **PR Review 端点**（给 GitHub Actions 用）。

```bash
docker build -t wuji-release-mcp mcp-server/
docker run -d \
  -e GITHUB_TOKEN=xxx \        # 拉取 PR diff & 版本信息
  -e ANTHROPIC_API_KEY=xxx \   # Claude API Key（只放服务器，不入 Actions）
  -e REVIEW_TOKEN=xxx \        # GitHub Actions 调用 /review 的鉴权 token
  -e MCP_TRANSPORT=http \
  -p 8080:8080 \
  wuji-release-mcp
```

端点说明：

| 端点 | 用途 |
|------|------|
| `GET /health` | 健康检查 |
| `GET /mcp/sse` | Claude Code MCP 连接 |
| `POST /review` | GitHub Actions 调用，触发 PR 多 Agent 审查 |

Claude Code `.mcp.json` 改为：

```json
{
  "mcpServers": {
    "wuji-release": {
      "type": "sse",
      "url": "http://内网地址:8080/mcp/sse"
    }
  }
}
```

---

## 子仓库接入

### PR 自动 Review

在子仓库添加 `.github/workflows/pr-review.yml`：

```yaml
name: Claude PR Review
on:
  pull_request:
    types: [opened, synchronize, ready_for_review]
jobs:
  # 快速 review（二选一或两个都加）
  quick:
    uses: wuji-technology/.github/.github/workflows/ci-pr-review.yml@main
    secrets:
      anthropic-api-key: ${{ secrets.ANTHROPIC_API_KEY }}
  # 多 Agent 深度 review（通过 Review 服务器，无需 ANTHROPIC_API_KEY）
  deep:
    uses: wuji-technology/.github/.github/workflows/ci-pr-agent-review.yml@main
    secrets:
      review-token: ${{ secrets.REVIEW_TOKEN }}
      review-server-url: ${{ secrets.REVIEW_SERVER_URL }}
```

- `ANTHROPIC_API_KEY`：Org 级别 Secrets，快速 review 用
- `REVIEW_TOKEN` / `REVIEW_SERVER_URL`：Org 级别 Secrets，指向部署的 Review 服务器

### Release 自动触发

在子仓库添加 `.github/workflows/release.yml`：

```yaml
name: Auto Release
on:
  push:
    tags: ['v*']
jobs:
  release:
    uses: wuji-technology/.github/.github/workflows/release-auto.yml@main
    secrets: inherit
```

### CHANGELOG 格式要求

所有仓库的 `CHANGELOG.md` 顶部必须保持 `## [Unreleased]` 占位：

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

## 脚本说明

### `scripts/release/update-changelog.py`

```bash
python3 scripts/release/update-changelog.py \
  --file CHANGELOG.md \
  --version 1.6.0 \
  --date 2026-05-01 \   # 可选，留空用今天
  --repo wujihandpy      # 可选，生成底部比较链接
```

### `scripts/release/update-versions.py`

```bash
python3 scripts/release/update-versions.py \
  --config .release.yml \
  --version 1.6.0 \
  --dry-run              # 可选，仅预览
```

### `scripts/docs/fetch-changelogs.py`

```bash
echo '[{"repo":"wujihandpy","version":"1.6.0","changelog_path":"CHANGELOG.md"}]' \
  | GITHUB_TOKEN=xxx python3 scripts/docs/fetch-changelogs.py > changelogs.json
```

---

## 配置要求

### 组织级 Secrets（Settings → Secrets）

| Secret | 用途 |
|--------|------|
| `AUTOMATION_APP_PRIVATE_KEY` | GitHub App 私钥，跨仓库操作 |
| `ANTHROPIC_API_KEY` | Claude API Key，快速 PR review 用（`ci-pr-review.yml`） |
| `REVIEW_TOKEN` | 调用 Review 服务器 `/review` 端点的鉴权 token |
| `REVIEW_SERVER_URL` | Review 服务器地址，如 `http://内网IP:8080` |
| `FEISHU_WEBHOOK_URL` | 飞书群机器人，发版通知（可选） |

### 组织级 Variables（Settings → Variables）

| Variable | 用途 |
|----------|------|
| `AUTOMATION_APP_ID` | GitHub App ID |

### Review 服务器环境变量

| 环境变量 | 用途 |
|----------|------|
| `GITHUB_TOKEN` | 拉取 PR diff 和版本信息 |
| `ANTHROPIC_API_KEY` | Claude API Key（只放服务器端） |
| `REVIEW_TOKEN` | 与 Org Secret 保持一致，用于鉴权 |
| `MCP_TRANSPORT` | 设为 `http` 启动 HTTP 模式 |
| `MCP_PORT` | 监听端口，默认 `8080` |
| `JIRA_BASE_URL` | **可选**，Jira Base URL（如 `https://your-company.atlassian.net/rest/api/3`） |
| `JIRA_SYNC_TO_JIRA` | **可选**，设 `true` 启用 Jira 自动回写（Blocker 退回 To Do） |
| `JIRA_BLOCKER_STATUS_ID` | **可选**，Blocker 时退回的 Jira 状态 ID（默认 "3"） |

启用 Jira 回写需在 Org Secrets 同时配置 `JIRA_API_TOKEN` 和 `JIRA_EMAIL` 即可。

### 各开发者本地

```bash
# ~/.zshrc 或 ~/.bashrc
export GITHUB_TOKEN=ghp_xxx       # GitHub PAT，有组织读写权限
export MCP_TOKEN=xxx               # MCP Server 鉴权 token（HTTP 模式）
```

---

## Contact

dev@wuji.tech"# Test AI Review" 
