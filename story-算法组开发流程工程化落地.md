# Story：算法组开发流程工程化落地

**标题**：`feat: 算法组开发流程工程化落地 — 自动化管线接入与规范强制执行`

**优先级**：High  
**预估工期**：6-9 个工作日（建议跨 1 个 Sprint，按阶段交付）

---

## 描述

基于《算法组 Sprint 开发流程》文档，将流程规范通过工程化手段落地到 wuji-technology 组织的算法仓库中，实现：分支/Commit/PR 规范自动检查、AI Code Review 自动触发、发版流程自动化、飞书通知闭环。确保算法组同学只需按文档操作，规范由 CI 强制保障。

---

## 验收标准 (Acceptance Criteria)

| # | 验收项 | 验证方式 |
|---|--------|----------|
| AC-1 | 算法仓库提 PR 后，自动触发规范检查（标题 Conventional Commits、描述含工作项关联、非 docs/chore PR 必须更新 CHANGELOG） | 提一个不合规 PR → 自动 comment 告警 |
| AC-2 | PR 自动触发 AI Review（快速 Review + 多 Agent 深度 Review） | PR 提交后 1-3min 内收到 Review 评论 |
| AC-3 | Review 中自动关联飞书项目单号，拉取 Jira 验收标准作为审查上下文 | Review 报告中包含"Jira 需求上下文"段落 |
| AC-4 | MCP Server 部署到云服务器，`/health`、`/review`、`/mcp/sse` 三个端点正常工作 | `curl /health` 返回 ok |
| AC-5 | 发版流程可通过 Claude Code 对话或 CLI 触发，CHANGELOG 自动更新 + PR 自动创建 | dry-run 触发一次发版预览成功 |
| AC-6 | 发版完成后飞书群收到通知 | 触发发版后飞书群出现卡片消息 |
| AC-7 | 算法子仓库接入文档齐全，包含 workflow 配置示例和 `.release.yml` 模板 | 按文档配置一个示例仓库，全流程跑通 |

---

## 子任务拆分

### 阶段一：基础设施部署（2-3天）

| 子任务 | 描述 | 预估 |
|--------|------|------|
| **1.1 MCP Server 云端部署** | Docker 构建 + 部署到云服务器，配置 `.env`（GitHub Token、DashScope、Jira PAT、飞书凭证），验证 `/health` 端点 | 0.5d |
| **1.2 Nginx 反向代理 + HTTPS** | 配置域名/反代，确保 GitHub Actions 可从公网访问 `/review` 端点 | 0.5d |
| **1.3 组织级 Secrets 配置** | 在 wuji-technology 组织设置 `REVIEW_TOKEN`、`REVIEW_SERVER_URL`、`ANTHROPIC_API_KEY`、`FEISHU_WEBHOOK_URL` 等 Secrets/Variables | 0.5d |
| **1.4 连通性验证** | 逐项验证 GitHub API → DashScope → Jira → 飞书 四条链路 | 0.5d |

### 阶段二：CI 管线接入（2-3天）

| 子任务 | 描述 | 预估 |
|--------|------|------|
| **2.1 算法仓库接入 PR 规范检查** | 在目标算法仓库添加 `.github/workflows/pr-review.yml`，复用 `ci-pr-review.yml` + `ci-pr-agent-review.yml` | 0.5d |
| **2.2 PR 标题/描述规范强制** | 确认 Review workflow 中的规范检查覆盖：Conventional Commits 标题、`Resolve m-xxx`/`Resolve f-xxx` 关联、CHANGELOG 更新检测 | 0.5d |
| **2.3 分支保护规则** | 在算法仓库 main 分支设置 Branch Protection：要求 PR Review 通过、CI 检查通过才能合入 | 0.5d |
| **2.4 端到端验证** | 在算法仓库提一个真实 PR，验证完整 Review 流程（规范检查 → AI Review → Jira 上下文注入） | 0.5d |

### 阶段三：发版流程接入（1-2天）

| 子任务 | 描述 | 预估 |
|--------|------|------|
| **3.1 算法仓库 CHANGELOG 初始化** | 在目标仓库创建/规范化 `CHANGELOG.md`，确保有 `## [Unreleased]` 占位 | 0.5d |
| **3.2 接入自动发版** | 添加 `.github/workflows/release.yml`（复用 `release-auto.yml`），配置 `.release.yml` 版本文件映射 | 0.5d |
| **3.3 发版 dry-run 验证** | 通过 CLI 或 MCP 对话执行 `dry-run` 发版，确认 CHANGELOG 预览正确 | 0.5d |

### 阶段四：通知与文档（1天）

| 子任务 | 描述 | 预估 |
|--------|------|------|
| **4.1 飞书通知验证** | 验证发版后飞书群通知正常（卡片消息格式、内容完整） | 0.5d |
| **4.2 算法组接入指南** | 编写面向算法组的快速接入文档：环境配置 → Claude Code 安装 → MCP 配置 → 日常操作 checklist | 0.5d |

---

## 技术依赖

| 依赖项 | 状态 |
|--------|------|
| GitHub Token (PAT) | ✅ 已验证 |
| DashScope API (Qwen-Max) | ✅ 已验证 |
| Jira API (PAT) | ✅ 已验证 |
| 飞书 API (App ID/Secret) | ✅ 已验证 |
| 云服务器（部署 MCP Server） | ⏳ 待确认 |
| 组织级 Secrets 配置权限 | ⏳ 待确认 |

---

## 风险项

1. **云服务器网络** — GitHub Actions 需要能访问到 Review Server，需确认公网可达或配置内网穿透
2. **Qwen-Max 效果** — 多 Agent Review 质量需要在真实 PR 上验证，可能需要调优 Prompt
3. **算法仓库差异** — 不同算法仓库的项目结构可能不同（Python/C++/ROS），CHANGELOG 和版本文件路径需逐仓库适配

---

## 关联信息

- 流程文档：《算法组 Sprint 开发流程（裁剪版）》
- 平台仓库：`wuji-technology/.github`
- MCP Server：`mcp-server/`
- Workflow 配置：`.github/workflows/`
