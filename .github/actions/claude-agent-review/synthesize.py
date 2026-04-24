#!/usr/bin/env python3
"""
综合对比两个 Agent 的 review 结果，输出最终统一报告。

两个 Agent 都标记的问题 → 高置信度，标注 ⚡ 共识
只有一个 Agent 标记的问题 → 标注来源，供参考
"""
import os
import re
import subprocess
import sys


def build_synthesis_prompt(review_a: str, review_b: str, language: str) -> str:
    if language == "zh":
        return f"""你是一名首席工程师，负责综合两位审查员的 PR review 意见，输出最终报告。请用中文。

## 审查员 A（安全与正确性）的意见：
{review_a}

---

## 审查员 B（架构与可维护性）的意见：
{review_b}

---

任务：
1. 找出两位审查员都提到的问题（共识问题）→ 高置信度，必须重视
2. 汇总只有一方提到的问题 → 标注来源
3. 给出整体结论和优先级排序

输出格式：
## 🤖 Claude Multi-Agent Review（综合报告）

### 整体结论
一句话总结本次 PR 质量。

### ⚡ 共识问题（两位审查员均提及，高置信度）
| 严重度 | 文件 | 描述 |
|--------|------|------|
| ... | ... | ... |

若无共识问题，写：**无共识问题** ✅

### 📋 其他问题
| 严重度 | 来源 | 文件 | 描述 |
|--------|------|------|------|
| ... | 安全审查/架构审查 | ... | ... |

### ✅ 共同认可的优点
两位审查员都认为做得好的地方。

### 📌 合入建议
- Blocker 数量：X 个（必须修复后才能合入）
- High 数量：X 个（强烈建议修复）
- 综合建议：[ 可以合入 / 修复 Blocker 后合入 / 需要较大改动 ]"""

    return f"""You are a principal engineer synthesizing two reviewers' PR feedback. Output in English.

## Reviewer A (Security & Correctness):
{review_a}

---

## Reviewer B (Architecture & Maintainability):
{review_b}

---

Tasks:
1. Find issues mentioned by BOTH reviewers (consensus) → high confidence, must address
2. List issues from only one reviewer → note the source
3. Give overall conclusion and priority ranking

Output format:
## 🤖 Claude Multi-Agent Review (Synthesis)

### Overall Verdict
One sentence on PR quality.

### ⚡ Consensus Issues (flagged by both — high confidence)
| Severity | File | Description |
|----------|------|-------------|
| ... | ... | ... |

If none: **No consensus issues** ✅

### 📋 Other Issues
| Severity | Source | File | Description |
|----------|--------|------|-------------|
| ... | Security/Architecture | ... | ... |

### ✅ Shared Positives
Things both reviewers agree are well done.

### 📌 Merge Recommendation
- Blockers: X (must fix before merge)
- High: X (strongly recommend fixing)
- Recommendation: [ Ready to merge / Fix blockers first / Needs significant rework ]"""


def main():
    language = os.environ.get("CLAUDE_LANGUAGE", "zh")
    model = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6")
    review_a_path = os.environ.get("REVIEW_A", "/tmp/review-security.md")
    review_b_path = os.environ.get("REVIEW_B", "/tmp/review-architecture.md")
    output_file = os.environ.get("SYNTHESIS_OUTPUT", "/tmp/synthesis-review.md")

    review_a = open(review_a_path).read() if os.path.exists(review_a_path) else "（未获取到）"
    review_b = open(review_b_path).read() if os.path.exists(review_b_path) else "（未获取到）"

    prompt = build_synthesis_prompt(review_a, review_b, language)

    result = subprocess.run(
        [
            "claude", "--print",
            "--model", model,
            "--allowedTools", "Read",
            prompt,
        ],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0 or not result.stdout.strip():
        # 降级：把两个 review 直接拼在一起
        fallback = f"{review_a}\n\n---\n\n{review_b}"
        with open(output_file, "w") as f:
            f.write(fallback)
        sys.exit(0)

    with open(output_file, "w") as f:
        f.write(result.stdout)
    print(result.stdout)


if __name__ == "__main__":
    main()