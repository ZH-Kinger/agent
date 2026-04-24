"""Tool: pr_review — 抓取 PR diff 并调用 LLM 多 Agent 进行审查，返回综合报告"""
import base64
import os
from openai import OpenAI
import httpx
from config import GITHUB_API, GITHUB_ORG, HEADERS, LLM_MODEL, LLM_MAX_TOKENS

from tools.jira import fetch_jira_issue, extract_jira_id_from_text, add_jira_comment, update_jira_status

# ── 系统 Prompt ────────────────────────────────────────────────────────────

_SYSTEM_SECURITY = """你是一名安全与正确性审查员，审查 Pull Request。请用中文输出。

审查重点：
1. 安全漏洞 — 注入、未校验输入、硬编码密钥、权限绕过
2. 逻辑正确性 — 边界条件、空指针、并发竞态、数据丢失风险
3. 错误处理 — 异常是否被吞掉、错误码是否正确传递
4. 依赖安全 — 新增依赖是否可信、版本是否锁定
5. Jira 验收标准 — 代码是否实现了需求中列出的验收标准（Acceptance Criteria）

严重级别：Blocker / High / Medium / Low

输出格式（严格遵守，内容会被后续步骤解析）：
## 🔐 Security & Correctness Review

### 总体评价
一句话。

### 问题清单
| 严重度 | 文件 | 描述 |
|--------|------|------|
| Blocker/High/Medium/Low | file:line | 描述 |

### 优点
1-3 条。

若无问题，问题清单写：| — | — | 无问题 |"""

_SYSTEM_ARCHITECTURE = """你是一名架构与可维护性审查员，审查 Pull Request。请用中文输出。

审查重点：
1. 设计合理性 — 职责是否单一、接口是否清晰、是否违反现有架构约定
2. 可维护性 — 重复代码、过度复杂、命名不清晰、缺少测试
3. 性能影响 — 不必要的循环、重复 IO、内存泄漏风险
4. 扩展性 — 是否对未来变更友好、是否引入不必要的耦合

严重级别：Blocker / High / Medium / Low

输出格式（严格遵守，内容会被后续步骤解析）：
## 🏗️ Architecture & Maintainability Review

### 总体评价
一句话。

### 问题清单
| 严重度 | 文件 | 描述 |
|--------|------|------|
| Blocker/High/Medium/Low | file:line | 描述 |

### 优点
1-3 条。

若无问题，问题清单写：| — | — | 无问题 |"""

_SYSTEM_SYNTHESIS = """你是一名首席工程师，综合两位审查员的意见输出最终报告。请用中文。

任务：
1. 找出两位审查员都提到的问题（共识）→ 高置信度
2. 汇总只有一方提到的问题，标注来源
3. 给出整体结论和合入建议

输出格式：
## 🤖 Claude Multi-Agent Review（综合报告）

### 整体结论
一句话。

### ⚡ 共识问题（两位审查员均提及）
| 严重度 | 文件 | 描述 |
|--------|------|------|

若无共识问题写：**无共识问题** ✅

### 📋 其他问题
| 严重度 | 来源 | 文件 | 描述 |
|--------|------|------|------|

### ✅ 共同认可的优点
两位都认为做得好的地方。

### 📌 合入建议
- Blocker 数量：X 个
- High 数量：X 个
- 综合建议：[ 可以合入 / 修复 Blocker 后合入 / 需要较大改动 ]"""


# ── 核心函数 ───────────────────────────────────────────────────────────────

def pr_review(repo: str, pr_number: int, title: str = "", body: str = "",
              language: str = "zh", max_diff_lines: int = 1500,
              jira_integration: dict = None) -> dict:
    """
    对指定 PR 进行多 Agent 审查，返回综合报告。

    Args:
        repo: 仓库名，如 wujihandpy
        pr_number: PR 编号
        title: PR 标题
        body: PR 描述
        language: 输出语言（zh/en，当前仅支持 zh）
        max_diff_lines: diff 最大行数
        jira_integration: 可选，Jira 集成配置
            {
                "sync_to_jira": True/False,  # 是否回写 Jira
                "status_mapping": {"blocker": "3"}  # Blocker → 要设的状态 id
            }

    Returns:
        {"ok": True, "review": "markdown", "jira_synced": False} 或 {"ok": False, "error": "..."}
    """
    # 1. 抓取 diff
    diff_result = _fetch_pr_diff(repo, pr_number, max_diff_lines)
    if not diff_result["ok"]:
        return diff_result
    diff = diff_result["diff"]

    if not diff.strip():
        return {"ok": True, "review": "✅ LGTM — diff 为空，无需审查。", "jira_synced": False}

    # 2. 提取 Jira ID 并拉取详情
    jira_id = extract_jira_id_from_text(body) or extract_jira_id_from_text(title)
    jira_context = "（无 Jira 关联）"

    if jira_id:
        jira_res = fetch_jira_issue(jira_id)
        if jira_res["ok"]:
            data = jira_res["data"]
            ac = data.get("acceptance_criteria") or "（未填写）"
            test_notes = data.get("test_notes") or "（无）"
            jira_context = f"""## 📋 Jira 需求上下文

**链接**: https://jira.example.com/browse/{jira_id}
**标题**: {data['summary']}

**验收标准 (Acceptance Criteria)**:
{ac if ac and isinstance(ac, str) else "(未填写)"}

**测试备注**:
{test_notes if test_notes and isinstance(test_notes, str) else "(无)"}
"""

    # 3. 规范检查（本地，无 API 费用）
    convention_warnings = _check_conventions(title, body, diff, jira_id)

    # 4. 拼接 user msg（Jira 上下文在最前，权重最高）
    user_msg = f"""{jira_context}

---

PR 标题：{title}

PR 描述：{body or '（无）'}

```diff
{diff}
```"""

    # 5. 两个 Agent 并行审查
    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        f_security = executor.submit(_call_llm, _SYSTEM_SECURITY, user_msg)
        f_arch = executor.submit(_call_llm, _SYSTEM_ARCHITECTURE, user_msg)
        review_security = f_security.result()
        review_arch = f_arch.result()

    # 6. 综合对比
    synthesis_msg = f"## 审查员 A（安全与正确性）：\n{review_security}\n\n---\n\n## 审查员 B（架构与可维护性）：\n{review_arch}"
    synthesis = _call_llm(_SYSTEM_SYNTHESIS, synthesis_msg)

    # 7. 拼接最终输出
    parts = []
    if convention_warnings:
        parts.append(convention_warnings)
    parts.append(synthesis)
    review = "\n\n---\n\n".join(parts)

    result = {"ok": True, "review": review, "jira_synced": False}

    # 8. Jira 回写（可选）
    if jira_id and jira_integration:
        sync_to_jira = jira_integration.get("sync_to_jira", False)
        status_mapping = jira_integration.get("status_mapping", {})

        if sync_to_jira:
            import re
            has_blocker = bool(re.search(r"\|^\| Blocker\|", review, re.MULTILINE))
            blocker_status_id = status_mapping.get("blocker")

            # 构造评论
            jira_comment = f"""## 🤖 AI PR Review 反馈

**结论**：{'✨ 可以通过，可合入' if not has_blocker else '❌ 发现 Blocker，建议退回'}

{review}
---
自动触发：[`ci-pr-agent-review.yml`](https://github.com/{GITHUB_ORG}/{repo}/pull/{pr_number})"""

            if has_blocker and blocker_status_id:
                # 退回 + 评论
                add_jira_comment(jira_id, jira_comment)
                update_jira_status(jira_id, blocker_status_id,
                                 comment="AI Review 发现 Blocker 问题，已退回待修正")
                result["jira_synced"] = True
                result["jira_action"] = "blocked_and_retuned"
            else:
                # 仅评论
                add_jira_comment(jira_id, jira_comment)
                result["jira_synced"] = True
                result["jira_action"] = "commented"

    return result


def _fetch_pr_diff(repo: str, pr_number: int, max_lines: int) -> dict:
    url = f"{GITHUB_API}/repos/{GITHUB_ORG}/{repo}/pulls/{pr_number}"
    try:
        resp = httpx.get(
            url,
            headers={**HEADERS, "Accept": "application/vnd.github.v3.diff"},
            timeout=30,
        )
        if resp.status_code == 404:
            return {"ok": False, "error": f"PR #{pr_number} 在 {repo} 中不存在"}
        resp.raise_for_status()
        lines = resp.text.splitlines()
        diff = "\n".join(lines[:max_lines])
        if len(lines) > max_lines:
            diff += f"\n\n... (diff 超过 {max_lines} 行，已截断)"
        return {"ok": True, "diff": diff}
    except Exception as e:
        return {"ok": False, "error": f"抓取 diff 失败：{e}"}


def _call_llm(system: str, user_msg: str) -> str:
    client = OpenAI()
    resp = client.chat.completions.create(
        model=LLM_MODEL,
        max_tokens=LLM_MAX_TOKENS,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_msg},
        ],
    )
    return resp.choices[0].message.content


def _check_conventions(title: str, body: str, diff: str, jira_id: str = None) -> str | None:
    import re
    warnings = []
    valid_prefix = re.compile(
        r"^(feat|fix|docs|style|refactor|perf|test|chore|ci|build|revert)(\(.+\))?\!?\:\s+\S",
        re.IGNORECASE,
    )

    if title and not valid_prefix.match(title):
        warnings.append(
            f"**PR 标题格式不符合规范**\n> 当前：`{title}`\n"
            "> 期望：`type(scope): description`，如 `feat: 新增登录功能`"
        )

    # Jira 关联检查 — 支持 JIRA-123 / PROJ-456 或 m-123 / f-456
    if body:
        if not (jira_id or re.search(r"\b[A-Z]+-[A-Z-]*\d+\b|\b[mf]-\d+\b", body, re.IGNORECASE)):
            warnings.append(
                "**PR 描述未关联工作项**\n> 请添加 `Resolve JIRA-123`、`Resolve m-xxx` 或 `Resolve f-xxx`"
            )

    if not re.match(r"^(docs|chore|style|ci)\b", title or "", re.IGNORECASE):
        if "CHANGELOG" not in diff:
            warnings.append(
                "**未检测到 CHANGELOG 更新**\n"
                "> 代码变更 PR 建议在 `## [Unreleased]` 下补充变更说明"
            )

    if not warnings:
        return None
    return "## ⚠️ PR 规范检查\n\n" + "\n\n".join(f"- {w}" for w in warnings)