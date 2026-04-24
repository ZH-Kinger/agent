#!/usr/bin/env python3
"""构建 review prompt 并调用 Claude Code Agent。

REVIEW_PERSONA 环境变量控制审查视角：
  security     — 安全与正确性（默认）
  architecture — 架构与可维护性
"""
import os
import subprocess
import sys

PERSONAS = {
    "security": {
        "zh": {
            "role": "安全与正确性审查员",
            "focus": """审查重点（安全与正确性视角）：
1. 安全漏洞 — 注入、未校验输入、硬编码密钥、权限绕过
2. 逻辑正确性 — 边界条件、空指针、并发竞态、数据丢失风险
3. 错误处理 — 异常是否被吞掉、错误码是否正确传递
4. 依赖安全 — 新增依赖是否可信、版本是否锁定""",
            "tag": "🔐 Security & Correctness",
        },
        "en": {
            "role": "Security & Correctness Reviewer",
            "focus": """Review focus (security & correctness perspective):
1. Security vulnerabilities — injection, unvalidated input, hardcoded secrets, auth bypass
2. Logic correctness — boundary conditions, null pointers, race conditions, data loss risk
3. Error handling — swallowed exceptions, error code propagation
4. Dependency safety — trustworthiness of new deps, version pinning""",
            "tag": "🔐 Security & Correctness",
        },
    },
    "architecture": {
        "zh": {
            "role": "架构与可维护性审查员",
            "focus": """审查重点（架构与可维护性视角）：
1. 设计合理性 — 职责是否单一、接口是否清晰、是否违反现有架构约定
2. 可维护性 — 重复代码、过度复杂、命名不清晰、缺少测试
3. 性能影响 — 不必要的循环、重复 IO、内存泄漏风险
4. 扩展性 — 是否对未来变更友好、是否引入不必要的耦合""",
            "tag": "🏗️ Architecture & Maintainability",
        },
        "en": {
            "role": "Architecture & Maintainability Reviewer",
            "focus": """Review focus (architecture & maintainability perspective):
1. Design soundness — single responsibility, clear interfaces, architecture convention compliance
2. Maintainability — code duplication, over-complexity, unclear naming, missing tests
3. Performance impact — unnecessary loops, repeated IO, memory leak risk
4. Extensibility — friendly to future changes, unnecessary coupling""",
            "tag": "🏗️ Architecture & Maintainability",
        },
    },
}


def build_prompt(title, author, base_branch, body, changed_files, language, persona):
    p = PERSONAS.get(persona, PERSONAS["security"])[language]

    if language == "zh":
        return f"""你是一名{p['role']}，正在审查以下 Pull Request。请用中文输出所有内容。

PR 信息：
- 标题：{title}
- 作者：{author}
- 目标分支：{base_branch}
- 描述：{body or '（无）'}

变更文件：
{changed_files}

{p['focus']}

审查步骤：
1. 读取 /tmp/pr.diff 了解变更
2. 主动用 Read 工具读取关键文件的上下文（被调用函数、配置、测试等）
3. 只从你的视角（{p['role']}）给出意见，不需要覆盖所有方面

严重级别：Blocker / High / Medium / Low

输出格式（严格遵守，输出内容会被后续 Agent 解析）：
## {p['tag']} Review

### 总体评价
一句话。

### 问题清单
| 严重度 | 文件 | 描述 |
|--------|------|------|
| Blocker/High/Medium/Low | file:line | 描述 |

### 优点
1-3 条。

若无问题，问题清单只写一行：| — | — | 无问题 |"""

    return f"""You are a {p['role']} reviewing the following Pull Request. Output in English.

PR Info:
- Title: {title}
- Author: {author}
- Base branch: {base_branch}
- Description: {body or '(none)'}

Changed files:
{changed_files}

{p['focus']}

Steps:
1. Read /tmp/pr.diff to understand the changes
2. Actively use Read tool for key file context (called functions, configs, tests)
3. Only review from your perspective ({p['role']}), no need to cover everything

Severity: Blocker / High / Medium / Low

Output format (strict — output will be parsed by a synthesis agent):
## {p['tag']} Review

### Summary
One sentence.

### Issues
| Severity | File | Description |
|----------|------|-------------|
| Blocker/High/Medium/Low | file:line | Description |

### Positives
1-3 items.

If no issues, write in Issues table: | — | — | No issues found |"""


def main():
    title = os.environ.get("PR_TITLE", "")
    author = os.environ.get("PR_AUTHOR", "")
    base_branch = os.environ.get("BASE_BRANCH", "main")
    language = os.environ.get("CLAUDE_LANGUAGE", "zh")
    model = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6")
    persona = os.environ.get("REVIEW_PERSONA", "security")
    output_file = os.environ.get("REVIEW_OUTPUT", "/tmp/agent-review.md")

    body = open("/tmp/pr-body.txt").read().strip() if os.path.exists("/tmp/pr-body.txt") else ""
    changed_files = open("/tmp/changed-files.txt").read().strip() if os.path.exists("/tmp/changed-files.txt") else ""

    prompt = build_prompt(title, author, base_branch, body, changed_files, language, persona)

    result = subprocess.run(
        [
            "claude", "--print",
            "--model", model,
            "--allowedTools", "Read,Glob,Grep,Bash(git*),Bash(cat /tmp/pr.diff)",
            prompt,
        ],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0 or not result.stdout.strip():
        msg = f"## 🤖 Review\n\n⚠️ {persona} review 生成失败。\n\n```\n{result.stderr[:500]}\n```"
        with open(output_file, "w") as f:
            f.write(msg)
        sys.exit(1)

    with open(output_file, "w") as f:
        f.write(result.stdout)
    print(result.stdout)


if __name__ == "__main__":
    main()