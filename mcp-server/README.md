# MCP Tools

本目录提供两种使用方式：

- **stdio 模式**：本地运行，适合个人使用 Claude Code
- **SSE 模式**：连接部署在服务器上的远端 MCP

## 安装

从 GitHub 直接安装：

```bash
pip install git+https://github.com/ZH-Kinger/agent.git#subdirectory=mcp-server
```

或克隆后本地安装（开发调试用）：

```bash
git clone https://github.com/ZH-Kinger/agent.git
pip install -e agent/mcp-server
```

安装后提供三个命令：
- `wuji-release-mcp` — MCP Server（stdio 或 HTTP）
- `wuji-release` — Release 命令行工具
- `wuji-review` — 仓库初始化与接入

## 一条命令初始化业务仓库

在目标业务仓库里执行：

```bash
wuji-review init --server-url http://<服务器IP>:8080 --bootstrap-token <BOOTSTRAP_TOKEN>
```

这个命令会自动：

- 写入 `.github/workflows/ci-pr-pipeline.yml`
- 写入 `.mcp.json`
- 检查 `gh auth status`
- 识别当前 GitHub 仓库
- 调服务端 `/bootstrap/register-repo` 申请仓库专属 `REVIEW_TOKEN`
- 自动写入 GitHub Secrets（`REVIEW_SERVER_URL` + `REVIEW_TOKEN`）
- 验证服务端 `/health`
- 输出测试 PR 的下一步

如果你只想检查状态：

```bash
wuji-review doctor --server-url http://<服务器IP>:8080
```

## 适合谁

- 想在 Claude Code 里直接调用 release / changelog / workflow 工具的开发者
- 想一条命令把业务仓库接入 Review + Claude MCP 的维护者
- 已经部署好服务端，准备做团队共享 MCP 接入的维护者

## 本地 stdio 模式

```json
{
  "mcpServers": {
    "wuji-release": {
      "type": "stdio",
      "command": "wuji-release-mcp",
      "env": {
        "GITHUB_TOKEN": "${GITHUB_TOKEN}",
        "GITHUB_ORG": "wuji-technology"
      }
    }
  }
}
```

## 远端 SSE 模式

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

## 常用能力

### Review 相关（CLI）

- `wuji-review init` — 一条命令初始化业务仓库
- `wuji-review doctor` — 检查接入状态和服务端连通性

### Release 相关（CLI / MCP）

- `suggest_next_version` — 推断下一版本号
- `get_current_versions` — 查询各仓库当前版本
- `fetch_changelog` — 获取指定版本的 CHANGELOG
- `validate_release_input` — 校验 repo=version 格式
- `preview_changelog` — dry-run 预览 CHANGELOG 更新
- `trigger_release` — 触发 release workflow
- `get_workflow_status` — 查询 workflow 运行状态

## 连接失败时

先检查：

- `GET /health` 是否返回 `ok`
- `GET /ready` 是否返回运行状态
- `GET /debug/config` 是否返回运行配置摘要
- `GET /mcp/sse` 是否能建立连接
- 服务器日志里是否出现 SSE 连接报错

平台部署与排障请看：`server-side/SETUP.md`
