# Release Automation

这个模块用于统一管理版本推断、CHANGELOG 预览、批量触发 release workflow。

## 适合谁

- 已经完成 PR Review 接入的团队
- 需要用 Claude Code 或 CLI 批量发版的维护者

## 核心能力

- 根据 `Unreleased` 自动推断下一个版本号
- dry-run 预览 CHANGELOG 更新
- 触发 `release-centralized.yml`
- 查询最近的 release workflow 状态

## 推荐使用顺序

1. `get_current_versions`
2. `suggest_next_version`
3. `preview_changelog`
4. `trigger_release(dry_run=true)`
5. `trigger_release`

## 前提

- 仓库有规范的 `CHANGELOG.md`
- 存在 `## [Unreleased]` 段落
- GitHub Token 有权限触发 workflow

## 入口

- Claude Code + MCP：看 `mcp-server/README.md`
- 平台整体说明：看 `README.md`
