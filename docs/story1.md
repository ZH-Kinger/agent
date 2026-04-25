# Story: 研发自动化协作平台（agent）

## 一、项目概述

| 项目 | 内容 |
|------|------|
| 名称 | wuji-technology/agent |
| 定位 | 面向研发团队的自动化协作平台 |
| 仓库 | https://github.com/ZH-Kinger/agent |
| 技术栈 | Python 3.11 / Starlette / Docker / GitHub Actions / Qwen-Max / 飞书开放平台 |
| 部署地址 | http://115.191.2.86:8080 |

## 二、核心能力矩阵

| 能力 | 状态 | 说明 |
|------|------|------|
| PR 标题规范检查 | 已上线 | Conventional Commits 格式校验 |
| PR 工作项引用检查 | 已上线 | 检查是否关联 Jira/m-xxx/f-xxx |
| AI Code Review | 已上线 | Qwen-Max 多 Agent 审查，评论到 PR |
| Jira 工单自动创建 | 已上线 | PR 描述无 Jira ID 时自动建单 |
| Jira 评论追加 | 已上线 | Review 完成后自动追加摘要评论 |
| 飞书群通知 | 已上线 | Review 结果卡片推送到飞书群 |
| 飞书审核人通知 | 已上线 | @ 指定审核人，要求审批 |
| 仓库专属 Token | 已上线 | 每个仓库独立的 wr_xxx 鉴权 |
| 一键初始化 | 已上线 | wuji-review init 两行命令接入 |
| 分支保护 | 已上线 | main 需 1 人审批 + CI 通过 |
| MCP 远端接入 | 已上线 | Claude Code 通过 SSE 连接 |
| Release 自动化 | 已就绪 | 版本推断 / CHANGELOG 更新 / 发版 |

## 三、系统架构

| 层级 | 组件 | 职责 |
|------|------|------|
| 触发层 | GitHub Actions | PR 创建/更新时触发 CI Pipeline |
| 网关层 | Review Server (Starlette) | HTTP API + MCP SSE 统一入口 |
| 智能层 | Qwen-Max (DashScope) | AI Code Review 多 Agent 分析 |
| 协作层 | Jira + 飞书 | 工单创建/关联 + 消息通知 |
| 管理层 | CLI + Bootstrap | 仓库注册/审核人配置/版本管理 |
| 部署层 | Docker Compose | 容器化部署，健康检查自愈 |

## 四、PR Pipeline 全流程

| 阶段 | 动作 | 触发方式 | 结果 |
|------|------|----------|------|
| 1. 提交 PR | 开发者 push feature 分支 | 手动 | 创建 PR |
| 2. 规范检查 | Convention Check Job | 自动 | 校验标题格式 + 工作项引用 |
| 3. AI 审查 | AI Code Review Job | 自动 | 调服务器 /pr-pipeline |
| 4. Jira 建单 | 服务端自动 | 自动 | 无 Jira ID 时创建工单 |
| 5. Jira 评论 | 服务端自动 | 自动 | 追加 Review 摘要到工单 |
| 6. 飞书群通知 | Review 结果卡片 | 自动 | 群内可见 Review 结论 |
| 7. 审核人通知 | 飞 @ 指定人 | 自动 | 审核人收到审批请求 |
| 8. 人工审批 | 审核人在 GitHub 审批 | 手动 | Approve / Request Changes |
| 9. 合入 main | 合并 PR | 手动 | 触发 Release（可选） |

## 五、服务端 API 清单

| 端点 | 方法 | 鉴权 | 用途 |
|------|------|------|------|
| `/health` | GET | 无 | 存活检查 |
| `/ready` | GET | 无 | 运行状态摘要 |
| `/debug/config` | GET | 无 | 配置摘要（脱敏） |
| `/review` | POST | REVIEW_TOKEN | 单独 AI Review |
| `/pr-pipeline` | POST | REVIEW_TOKEN | Jira + Review + 飞书 + 审核人通知 |
| `/bootstrap/register-repo` | POST | BOOTSTRAP_TOKEN | 签发仓库专属 Token |
| `/reviewers/{org}/{repo}` | GET | 无 | 查看仓库审核人 |
| `/reviewers` | POST | BOOTSTRAP_TOKEN | 设置仓库审核人 |
| `/mcp/sse` | GET | 无 | MCP SSE 连接入口 |
| `/mcp/messages` | POST | 无 | MCP 消息通道 |

## 六、Token 安全体系

| Token | 格式 | 持有者 | 用途 | 生命周期 |
|-------|------|--------|------|----------|
| `BOOTSTRAP_TOKEN` | 自定义字符串 | 管理员 | 注册新仓库、设置审核人 | 长期，在 .env 中配置 |
| `REVIEW_TOKEN`（全局） | 自定义字符串 | 所有仓库（旧模式） | GitHub Actions 调 API | 长期，在 .env 中配置 |
| `REVIEW_TOKEN`（仓库专属） | `wr_xxxxxx` | 单个仓库 | GitHub Actions 调 API | 创建后持久化，不失效 |

### Token 鉴权优先级

| 优先级 | 模式 | 条件 |
|--------|------|------|
| 1 | 仓库专属 | `REPO_TOKENS_FILE` 已配置且该仓库有记录 |
| 2 | 全局共享 | 回退到 `REVIEW_TOKEN` |
| 3 | 开放 | 均未配置（不推荐） |

## 七、审核人配置

| 操作 | 方式 | 鉴权 |
|------|------|------|
| 查看审核人 | `GET /reviewers/{org}/{repo}` | 无 |
| 设置审核人 | `POST /reviewers` | BOOTSTRAP_TOKEN |

### 设置审核人示例

```json
POST /reviewers
Authorization: Bearer wuji1234

{
  "repo_full_name": "ZH-Kinger/agent",
  "reviewers": [
    {"open_id": "ou_abc123", "name": "张三"},
    {"open_id": "ou_def456", "name": "李四"}
  ]
}
```

### 通知效果

| 通道 | 内容 | 触发时机 |
|------|------|----------|
| 飞书个人消息 | @ 审核人 + PR 信息 + 审核按钮 | PR Pipeline 完成后 |
| 飞书群消息 | Review 结果卡片 | PR Pipeline 完成后 |

## 八、分支保护规则

| 规则 | 配置 |
|------|------|
| 合入要求 | 1 人 Code Review 审批 |
| 必须通过的 CI | PR Convention Check + AI Code Review |
| 新 push 后 | 自动 dismiss 旧审批 |
| 分支必须最新 | 合入前需 rebase 到最新 main |

## 九、业务仓库接入方式

| 方式 | 步骤 | 适用场景 |
|------|------|----------|
| 自动接入（推荐） | `wuji-review init` | 有 gh CLI + 管理员权限 |
| 手动接入 | 复制 workflow + 配置 Secrets | 无 gh 或权限受限 |

### 自动接入

| 步骤 | 命令/操作 |
|------|-----------|
| 1. 安装工具 | `pip install git+https://github.com/ZH-Kinger/agent.git#subdirectory=mcp-server` |
| 2. 执行初始化 | `wuji-review init --server-url http://115.191.2.86:8080 --bootstrap-token <TOKEN>` |
| 3. 提交变更 | `git add . && git commit -m "ci: bootstrap wuji review" && git push` |
| 4. 测试 PR | 标题: `feat: test review pipeline`，描述: `Resolve m-000001` |

### 手动接入

| 步骤 | 操作 |
|------|------|
| 1 | 复制 `github-side/workflows/ci-pr-pipeline.yml` 到 `.github/workflows/` |
| 2 | GitHub Secrets 添加 `REVIEW_SERVER_URL` = `http://115.191.2.86:8080` |
| 3 | GitHub Secrets 添加 `REVIEW_TOKEN` = 仓库专属 token |
| 4 | 提测试 PR 验证 |

## 十、版本控制流程

| 步骤 | 工具/命令 | 说明 |
|------|-----------|------|
| 1. 查当前版本 | `wuji-release versions` | 查各仓库已发布版本 |
| 2. 推断版本号 | `wuji-release next-version <repo>` | 根据 Unreleased 内容自动推断 |
| 3. 预览 CHANGELOG | `wuji-release trigger "repo=1.0.0" --dry-run` | 不创建 PR，只看效果 |
| 4. 正式发版 | `wuji-release trigger "repo=1.0.0"` | 更新 CHANGELOG + 创建 Release PR |

### 版本号推断规则

| Unreleased 内容 | 版本变化 | 示例 |
|------------------|----------|------|
| 含 Added / 新增 | minor +1 | 1.5.0 → 1.6.0 |
| 含 Fixed / 修复 | patch +1 | 1.5.0 → 1.5.1 |
| 含 Removed / Breaking | major +1 | 1.5.0 → 2.0.0 |

## 十一、环境变量清单

| 分类 | 变量 | 必填 | 说明 |
|------|------|------|------|
| GitHub | `GITHUB_TOKEN` | 是 | GitHub PAT |
| GitHub | `GITHUB_ORG` | 否 | 组织名，默认 wuji-technology |
| LLM | `OPENAI_API_KEY` | 是 | DashScope API Key |
| LLM | `OPENAI_BASE_URL` | 否 | DashScope 接口地址 |
| LLM | `LLM_MODEL` | 否 | 默认 qwen-max |
| Jira | `JIRA_URL` | 否 | Jira 地址 |
| Jira | `JIRA_PAT` | 否 | Jira PAT |
| Jira | `JIRA_SYNC_TO_JIRA` | 否 | true 开启自动建单 |
| 飞书 | `FEISHU_APP_ID` | 否 | 飞书应用 ID |
| 飞书 | `FEISHU_APP_SECRET` | 否 | 飞书应用 Secret |
| 飞书 | `FEISHU_CHAT_ID` | 否 | 通知群 ID |
| 服务 | `MCP_TRANSPORT` | 否 | http/stdio |
| 服务 | `MCP_PORT` | 否 | 默认 8080 |
| 服务 | `REVIEW_TOKEN` | 否 | 全局共享 Token（旧模式） |
| 服务 | `BOOTSTRAP_TOKEN` | 推荐 | 管理员口令（新模式） |
| 服务 | `REPO_TOKENS_FILE` | 推荐 | 仓库 Token 持久化路径 |
| 服务 | `REVIEWERS_FILE` | 推荐 | 审核人持久化路径 |

## 十二、当前部署状态

| 检查项 | 状态 | 详情 |
|--------|------|------|
| 服务健康 | OK | `/health` 返回 200 |
| DashScope/LLM | OK | Qwen-Max 调用正常 |
| GitHub API | OK | 认证用户 ZH-Kinger |
| Jira | OK | 连接正常，自动建单已开启 |
| 飞书 | OK | tenant_access_token 正常 |
| MCP SSE | OK | 返回 session_id |
| Bootstrap | OK | 仓库注册正常 |
| 审核人 | OK | API 可用，持久化正常 |
| 分支保护 | OK | main 需审批 + CI |
