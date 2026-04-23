#!/usr/bin/env python3
"""Claude PR review script — called by the claude-review composite action."""

import argparse
import sys
import anthropic

SYSTEM_ZH = """你是一名资深工程师，负责 Pull Request 代码审查。
审查重点（按优先级）：
1. 正确性 — 逻辑错误、边界情况、潜在 bug
2. 安全性 — 注入、硬编码密钥、权限问题
3. 可维护性 — 命名清晰度、重复代码、过度复杂
4. 测试覆盖 — 关键路径是否有测试

输出格式（Markdown）：
## 🤖 Claude Code Review

### 总体评价
一句话总结。

### 问题清单
| 严重度 | 文件 | 描述 |
|--------|------|------|
| 🔴 阻塞 / 🟡 建议 / 🟢 备注 | `file:line` | 问题描述 |

### 优点
简短列出做得好的地方。

### 建议
如有整体性建议，在此说明。

如无问题，只输出"✅ LGTM — 无明显问题"。
不要重复整个 diff，只引用关键行。"""

SYSTEM_EN = """You are a senior engineer performing a Pull Request code review.
Review priorities:
1. Correctness — logic errors, edge cases, potential bugs
2. Security — injection, hardcoded secrets, permission issues
3. Maintainability — naming clarity, duplication, excessive complexity
4. Test coverage — critical paths covered

Output format (Markdown):
## 🤖 Claude Code Review

### Summary
One-sentence overall assessment.

### Issues
| Severity | File | Description |
|----------|------|-------------|
| 🔴 Blocker / 🟡 Suggestion / 🟢 Note | `file:line` | Description |

### Positives
Brief list of things done well.

### Recommendations
Any high-level recommendations.

If no issues found, output only "✅ LGTM — no significant issues"."""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--diff", required=True)
    parser.add_argument("--title", default="")
    parser.add_argument("--body", default="")
    parser.add_argument("--model", default="claude-sonnet-4-5")
    parser.add_argument("--language", default="zh", choices=["zh", "en"])
    args = parser.parse_args()

    with open(args.diff) as f:
        diff = f.read()

    if not diff.strip():
        print("✅ LGTM — diff is empty, nothing to review.")
        return

    system = SYSTEM_ZH if args.language == "zh" else SYSTEM_EN

    user_msg = f"PR Title: {args.title}\n\nPR Description:\n{args.body}\n\n```diff\n{diff}\n```"

    client = anthropic.Anthropic()
    message = client.messages.create(
        model=args.model,
        max_tokens=2048,
        system=system,
        messages=[{"role": "user", "content": user_msg}],
    )

    print(message.content[0].text)


if __name__ == "__main__":
    main()