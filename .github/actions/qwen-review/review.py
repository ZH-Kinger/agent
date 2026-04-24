#!/usr/bin/env python3
"""Qwen PR review script — OpenAI-compatible API (DashScope / Qwen-Max)."""

import argparse
import re
import sys
from openai import OpenAI

# PR 标题合法前缀（Conventional Commits）
_VALID_PREFIXES = (
    "feat", "fix", "docs", "style", "refactor",
    "perf", "test", "chore", "ci", "build", "revert",
)
# 工作项关联正则（Resolve m-xxx 或 f-xxx，或 JIRA-123 格式）
_WORK_ITEM_RE = re.compile(
    r"\b[Rr]esolve[sd]?\s+[mf]-\d+|\b[A-Z]+-\d+",
    re.IGNORECASE,
)

SYSTEM_ZH = """你是一名资深工程师，负责 Pull Request 代码审查。

严重级别定义：
- **Blocker**：必须修复才能合入，如逻辑错误、安全漏洞、数据丢失风险
- **High**：强烈建议修复，如性能问题、缺少错误处理、不符合架构规范
- **Medium**：建议改进，如代码重复、命名不清晰、缺少测试
- **Low**：可选优化，如注释缺失、风格问题

审查重点（按优先级）：
1. 正确性 — 逻辑错误、边界情况、潜在 bug
2. 安全性 — 注入、硬编码密钥、权限问题
3. 架构合规 — 是否符合项目规范，参数传递是否正确，配置项是否一致
4. 可维护性 — 命名清晰度、重复代码、过度复杂
5. 测试覆盖 — 关键路径是否有测试

输出格式（Markdown，严格遵守）：
## 🤖 AI Code Review (Qwen)

### 总体评价
一句话总结。

### 问题清单
| 严重度 | 文件 | 描述 |
|--------|------|------|
| Blocker / High / Medium / Low | `file:line` | 问题描述 |

### 优点
简短列出做得好的地方（1-3 条）。

### 建议
如有整体性建议，在此说明。

规则：
- 如无任何问题，只输出 "✅ LGTM — 无明显问题"
- 不要重复整个 diff，只引用关键行
- Blocker 问题必须明确指出修复方向"""

SYSTEM_EN = """You are a senior engineer performing a Pull Request code review.

Severity levels:
- **Blocker**: Must fix before merge — logic errors, security vulnerabilities, data loss risk
- **High**: Strongly recommended to fix — performance issues, missing error handling, architecture violations
- **Medium**: Suggested improvements — code duplication, unclear naming, missing tests
- **Low**: Optional — missing comments, style issues

Review priorities:
1. Correctness — logic errors, edge cases, potential bugs
2. Security — injection, hardcoded secrets, permission issues
3. Architecture compliance — follows project conventions, correct parameter passing, consistent config
4. Maintainability — naming clarity, duplication, excessive complexity
5. Test coverage — critical paths covered

Output format (Markdown, strictly follow):
## 🤖 AI Code Review (Qwen)

### Summary
One-sentence overall assessment.

### Issues
| Severity | File | Description |
|----------|------|-------------|
| Blocker / High / Medium / Low | `file:line` | Description |

### Positives
Brief list of things done well (1-3 items).

### Recommendations
Any high-level recommendations.

Rules:
- If no issues found, output only "✅ LGTM — no significant issues"
- Do not repeat the entire diff, only reference key lines
- Blocker issues must include a clear fix direction"""


def check_pr_conventions(title: str, body: str, diff: str, language: str) -> str | None:
    """
    检查 PR 规范：标题格式、工作项关联、CHANGELOG 更新。
    返回警告文本，若全部通过返回 None。
    """
    warnings = []

    # 1. 标题格式检查（Conventional Commits）
    prefix_pattern = re.compile(
        r"^(" + "|".join(_VALID_PREFIXES) + r")(\(.+\))?!?:\s+\S",
        re.IGNORECASE,
    )
    if title and not prefix_pattern.match(title):
        if language == "zh":
            warnings.append(
                f"**PR 标题格式不符合规范**\n"
                f"> 当前标题：`{title}`\n"
                f"> 期望格式：`type(scope): description`，"
                f"type 应为 `feat` / `fix` / `docs` / `chore` 等"
            )
        else:
            warnings.append(
                f"**PR title does not follow Conventional Commits**\n"
                f"> Current: `{title}`\n"
                f"> Expected: `type(scope): description` — "
                f"type should be `feat` / `fix` / `docs` / `chore` etc."
            )

    # 2. 工作项关联检查
    if body and not _WORK_ITEM_RE.search(body):
        if language == "zh":
            warnings.append(
                "**PR 描述未关联工作项**\n"
                "> 请在描述中添加 `Resolve m-xxx` 或 `Resolve f-xxx`"
            )
        else:
            warnings.append(
                "**PR description missing work item reference**\n"
                "> Please add `Resolve m-xxx` or `Resolve f-xxx` in the description"
            )

    # 3. CHANGELOG 检查（非 docs/chore PR 应更新 CHANGELOG）
    is_docs_or_chore = re.match(r"^(docs|chore|style|ci)\b", title or "", re.IGNORECASE)
    has_changelog = "CHANGELOG" in diff
    if not is_docs_or_chore and not has_changelog:
        if language == "zh":
            warnings.append(
                "**未检测到 CHANGELOG 更新**\n"
                "> 代码变更 PR 建议在 `CHANGELOG.md` 的 `## [Unreleased]` 下补充变更说明"
            )
        else:
            warnings.append(
                "**No CHANGELOG update detected**\n"
                "> Code change PRs should update `## [Unreleased]` in `CHANGELOG.md`"
            )

    if not warnings:
        return None

    header = "## ⚠️ PR 规范检查" if language == "zh" else "## ⚠️ PR Convention Check"
    return header + "\n\n" + "\n\n".join(f"- {w}" for w in warnings)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--diff", required=True)
    parser.add_argument("--title", default="")
    parser.add_argument("--body", default="")
    parser.add_argument("--model", default="qwen-max")
    parser.add_argument("--language", default="zh", choices=["zh", "en"])
    args = parser.parse_args()

    with open(args.diff) as f:
        diff = f.read()

    if not diff.strip():
        print("✅ LGTM — diff is empty, nothing to review.")
        return

    # PR 规范检查（本地，无 API 费用）
    convention_warnings = check_pr_conventions(args.title, args.body, diff, args.language)

    # LLM 代码审查（OpenAI 兼容接口）
    system = SYSTEM_ZH if args.language == "zh" else SYSTEM_EN
    user_msg = f"PR Title: {args.title}\n\nPR Description:\n{args.body}\n\n```diff\n{diff}\n```"

    client = OpenAI()
    response = client.chat.completions.create(
        model=args.model,
        max_tokens=2048,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_msg},
        ],
    )
    review_text = response.choices[0].message.content

    # 拼接输出：规范检查在前，代码审查在后
    output_parts = []
    if convention_warnings:
        output_parts.append(convention_warnings)
    output_parts.append(review_text)
    print("\n\n---\n\n".join(output_parts))


if __name__ == "__main__":
    main()
