# wuji-technology/.github

wuji-technology 组织的集中式自动化仓库，管理 Release 流程、PR Review、MCP 工具。

## 发版操作

发版前先推断版本号，再触发：

```
> wujihandpy 下一版该发什么？       → suggest_next_version
> dry run 发 wujihandpy=1.6.0      → trigger_release(dry_run=true)
> 确认，正式发                      → trigger_release
> 最近发版有没有失败？               → get_workflow_status
```

输入格式：`repo=version`，私有仓库：`repo=version:public/CHANGELOG.md`

版本推断规则：
- Unreleased 含 `Added` / `新增` → minor（1.5.0 → 1.6.0）
- Unreleased 含 `Fixed` / `修复` → patch（1.5.0 → 1.5.1）
- Unreleased 含 `Removed` / `Breaking` → major（1.5.0 → 2.0.0）

## CHANGELOG 规范

所有子仓库必须保持 `## [Unreleased]` 占位，发版时自动替换。

## MCP 工具列表

| 工具 | 用途 |
|------|------|
| `get_current_versions` | 查各仓库当前版本 |
| `suggest_next_version` | 推断下一版本号 |
| `validate_release_input` | 校验 repo=version 格式 |
| `preview_changelog` | dry-run 预览 CHANGELOG 更新 |
| `trigger_release` | 触发 release-centralized workflow |
| `get_workflow_status` | 查 workflow 运行状态 |
| `fetch_changelog` | 读某版本的 CHANGELOG 内容 |

## 脚本位置

- `scripts/release/` — CHANGELOG 更新、版本文件更新、输入解析
- `scripts/docs/` — 收集 CHANGELOG、生成 release-notes.mdx
- `mcp-server/` — MCP Server 和 CLI 工具
- `.github/actions/` — PR Review composite actions