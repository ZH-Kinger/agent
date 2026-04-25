# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/2-0-0.html).

## [Unreleased]

### Added
- AI PR Review 集成（Qwen-Max via DashScope）
- PR 规范自动检查（Conventional Commits、工作项关联）
- Release 自动化 workflow
- `/bootstrap/register-repo` 端点：为每个仓库签发专属 REVIEW_TOKEN
- `/ready`、`/debug/config` 诊断端点
- `wuji-review init` 一条命令完成业务仓库初始化（workflow + MCP + Secrets）
- `wuji-review doctor` 接入状态检查
- Token 分发流程：BOOTSTRAP_TOKEN 管理员口令 + 仓库专属 wr_xxx token
- Docker 部署支持（docker-compose + Dockerfile）

### Fixed
- MCP SSE 端点 `/mcp/sse` 签名兼容问题（Starlette Route handler）
