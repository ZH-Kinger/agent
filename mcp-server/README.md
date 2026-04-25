# MCP Tools

本目录提供两种使用方式：

- **stdio 模式**：本地运行，适合个人使用 Claude Code
- **SSE 模式**：连接部署在服务器上的远端 MCP

## 一条命令初始化

如果你想把接入流程压到最低，直接在目标业务仓库里执行：

```bash
pip install -e /path/to/mcp-server
wuji-review init --server-url http://<服务器IP>:8080 --review-token <REVIEW_TOKEN>
```

这个命令会自动：

- 写入 `.github/workflows/ci-pr-pipeline.yml`
- 写入 `.mcp.json`
- 检查 `gh auth status`
- 在可用时自动写入 GitHub Secrets
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

- `wuji-review init`
- `wuji-review doctor`
- `suggest_next_version`
- `get_current_versions`
- `fetch_changelog`
- `trigger_release`
- `get_workflow_status`

## 连接失败时

先检查：

- `GET /health` 是否返回 `ok`
- `GET /ready` 是否返回运行状态
- `GET /debug/config` 是否返回运行配置摘要
- `GET /mcp/sse` 是否能建立连接
- 服务器日志里是否出现 SSE 连接报错

平台部署与排障请看：`server-side/SETUP.md`
